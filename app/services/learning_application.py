"""Atomic, idempotent application of a persisted Writing evaluation (P3-10).

One successful transaction creates exactly:

- 1 ``LearningUpdate`` anchor,
- 4 ``LearningEvidence`` rows (one per canonical skill),
- 4 materialized ``LearnerSkillState`` rows (full canonical replay/rebuild),
- 1 ``PracticeRecommendation`` decision (practice or no_practice).

Semantics:

- idempotent: same learner + same evaluation returns the existing logical
  result with no duplicate effects;
- cross-owner: applying an already-owned evaluation to another learner is an
  explicit conflict;
- late arrival: every apply rebuilds the four skill states from the complete
  accepted evidence set under canonical source order, so arrival order never
  controls state;
- failure: any Phase 3 stage failure rolls back all Phase 3 writes;
- the transaction contains no provider/LLM call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.learner.planning_policy import PLANNER_VERSION
from app.learner.planner import plan_practice
from app.learner.state_engine import rebuild_all_skill_states
from app.learner.writing_evidence import (
    ExtractedWritingEvidence,
    ExtractedWritingEvidenceSet,
    WritingEvidenceExtractionError,
    extract_writing_evidence,
)
from app.learner.writing_policy import (
    WRITING_SKILLS,
    WRITING_SKILL_TAXONOMY_VERSION,
    WRITING_STATE_POLICY_VERSION,
)
from app.models.learning import (
    Learner,
    LearnerSkillState as LearnerSkillStateModel,
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
)
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.common import BandScore
from app.schemas.learner import (
    LearnerSkillState as LearnerSkillStateSchema,
    LearnerSkillStateSet,
)
from app.schemas.planning import (
    DecisionType,
    PlannerReasonCode,
    PracticeRecommendationDecision,
)
from app.schemas.writing import EvaluationMetadata


class LearningApplicationError(Exception):
    """Base error for the learning application service."""


class LearnerNotFoundError(LearningApplicationError):
    """The referenced learner does not exist."""


class EvaluationNotFoundError(LearningApplicationError):
    """The referenced persisted evaluation (or its attempt) does not exist."""


class CrossOwnerConflictError(LearningApplicationError):
    """The evaluation is already applied to a different learner."""


class LearningSourceError(LearningApplicationError):
    """The persisted source data cannot produce canonical evidence."""


@dataclass(frozen=True)
class AppliedLearningResult:
    """The logical outcome of applying one evaluation to a learner."""

    learning_update_id: int
    recommendation: PracticeRecommendationDecision
    reused: bool = False


def _set_items(
    evidence_set: ExtractedWritingEvidenceSet,
) -> list[ExtractedWritingEvidence]:
    return [getattr(evidence_set, skill) for skill in WRITING_SKILLS]


def _extracted_from_row(row: LearningEvidence) -> ExtractedWritingEvidence:
    """Map one persisted evidence row back into extraction-owned values for
    canonical replay. All fields are persisted source copies, so the replay is
    reproducible from the database alone."""

    return ExtractedWritingEvidence(
        writing_evaluation_id=row.writing_evaluation_id,
        skill=row.skill,
        observed_band=BandScore(value=row.observed_band),
        source_created_at=row.source_created_at,
        source_attempt_id=row.source_attempt_id,
        provenance=EvaluationMetadata(
            provider=row.provider,
            model=row.model,
            prompt_version=row.prompt_version,
            rubric_version=row.rubric_version,
            scoring_policy_version=row.scoring_policy_version,
            thinking_mode=row.thinking_mode,
        ),
    )


def _reconstruct_decision(
    row: PracticeRecommendation,
) -> PracticeRecommendationDecision:
    """Rebuild the audit decision from a persisted recommendation row."""

    return PracticeRecommendationDecision(
        decision_type=DecisionType(row.decision_type),
        target_skill=row.target_skill,
        learner_target_band=(
            BandScore(value=Decimal(row.learner_target_band))
            if row.learner_target_band is not None
            else None
        ),
        current_estimate=row.current_estimate,
        reason_codes=[PlannerReasonCode(code) for code in row.reason_codes],
        planner_version=row.planner_version,
        state_snapshot=LearnerSkillStateSet.model_validate(row.state_snapshot),
    )


def _resolve_existing(
    session: Session,
    *,
    learner_id: int,
    writing_evaluation_id: int,
) -> AppliedLearningResult:
    """Resolve an already-persisted update: idempotent replay or conflict."""

    existing = session.scalar(
        select(LearningUpdate).where(
            LearningUpdate.writing_evaluation_id == writing_evaluation_id
        )
    )
    if existing is None:
        raise LearningApplicationError(
            "existing learning update disappeared during application"
        )
    if existing.learner_id != learner_id:
        raise CrossOwnerConflictError(
            f"writing evaluation {writing_evaluation_id} is already applied "
            f"to learner {existing.learner_id}"
        )
    recommendation = session.scalar(
        select(PracticeRecommendation).where(
            PracticeRecommendation.learning_update_id == existing.id
        )
    )
    if recommendation is None:
        raise LearningApplicationError(
            f"learning update {existing.id} has no persisted recommendation"
        )
    return AppliedLearningResult(
        learning_update_id=existing.id,
        recommendation=_reconstruct_decision(recommendation),
        reused=True,
    )


def apply_writing_evaluation(
    session: Session,
    *,
    learner_id: int,
    writing_evaluation_id: int,
) -> AppliedLearningResult:
    """Apply one persisted evaluation to one learner atomically.

    The service owns only orchestration and persistence; extraction (P3-06),
    state replay (P3-07), and planning (P3-09) remain pure deterministic
    components. No provider/LLM call occurs inside the transaction.

    The read path autobegins a session transaction, so the write path joins
    that same transaction and commits it explicitly; any failure rolls back
    all Phase 3 writes. A uniqueness violation (concurrent duplicate) is
    resolved to idempotent replay or an explicit cross-owner conflict.
    """

    learner = session.get(Learner, learner_id)
    if learner is None:
        raise LearnerNotFoundError(f"learner {learner_id} not found")

    evaluation = session.get(WritingEvaluation, writing_evaluation_id)
    if evaluation is None:
        raise EvaluationNotFoundError(
            f"writing evaluation {writing_evaluation_id} not found"
        )
    attempt = session.get(WritingAttempt, evaluation.attempt_id)
    if attempt is None:
        raise EvaluationNotFoundError(
            f"attempt {evaluation.attempt_id} for evaluation "
            f"{writing_evaluation_id} not found"
        )

    try:
        extracted = extract_writing_evidence(evaluation, attempt)
    except WritingEvidenceExtractionError as error:
        raise LearningSourceError(str(error)) from error

    try:
        # Serialize concurrent applications to the same learner with a row
        # lock on the learner itself. This guarantees that the full canonical
        # rebuild below observes every committed evidence row for the learner,
        # so transaction completion order can never override canonical source
        # order. Different learners never contend and there is no lock-ordering
        # cycle, so bounded deadlock risk is avoided by construction.
        session.execute(
            select(Learner.id)
            .where(Learner.id == learner_id)
            .with_for_update()
        )

        # Idempotency re-check under the learner lock: a concurrent duplicate
        # application that committed before we acquired the lock is resolved
        # here without attempting any Phase 3 write.
        existing = session.scalar(
            select(LearningUpdate).where(
                LearningUpdate.writing_evaluation_id == writing_evaluation_id
            )
        )
        if existing is not None:
            session.rollback()
            return _resolve_existing(
                session,
                learner_id=learner_id,
                writing_evaluation_id=writing_evaluation_id,
            )

        learning_update = LearningUpdate(
            learner_id=learner_id,
            writing_evaluation_id=writing_evaluation_id,
            skill_taxonomy_version=WRITING_SKILL_TAXONOMY_VERSION,
            state_policy_version=WRITING_STATE_POLICY_VERSION,
            planner_version=PLANNER_VERSION,
        )
        session.add(learning_update)
        session.flush()

        evidence_rows = [
            LearningEvidence(
                learning_update_id=learning_update.id,
                learner_id=learner_id,
                writing_evaluation_id=writing_evaluation_id,
                skill=item.skill,
                observed_band=item.observed_band.value,
                source_created_at=item.source_created_at,
                source_attempt_id=item.source_attempt_id,
                provider=item.provenance.provider,
                model=item.provenance.model,
                prompt_version=item.provenance.prompt_version,
                rubric_version=item.provenance.rubric_version,
                scoring_policy_version=item.provenance.scoring_policy_version,
                thinking_mode=item.provenance.thinking_mode,
            )
            for item in _set_items(extracted)
        ]
        session.add_all(evidence_rows)
        session.flush()

        # Full canonical rebuild from every accepted evidence row for this
        # learner, so late-arriving older evidence cannot change semantics.
        all_rows = list(
            session.scalars(
                select(LearningEvidence).where(
                    LearningEvidence.learner_id == learner_id
                )
            ).all()
        )
        items = [_extracted_from_row(row) for row in all_rows]
        states = rebuild_all_skill_states(
            items,
            state_policy_version=WRITING_STATE_POLICY_VERSION,
        )
        last_evidence_ids = {
            (row.writing_evaluation_id, row.skill): row.id
            for row in all_rows
        }
        now = datetime.now(timezone.utc)

        materialized: dict[str, LearnerSkillStateSchema] = {}
        for skill in WRITING_SKILLS:
            computed = states[skill]
            last_evidence_id = (
                last_evidence_ids[
                    (computed.last_evidence_writing_evaluation_id, skill)
                ]
                if computed.last_evidence_writing_evaluation_id is not None
                else None
            )
            row = session.get(LearnerSkillStateModel, (learner_id, skill))
            revision = 1 if row is None else row.revision + 1
            if row is None:
                row = LearnerSkillStateModel(
                    learner_id=learner_id,
                    skill=skill,
                    estimated_band=computed.estimated_band,
                    evidence_count=computed.evidence_count,
                    state_policy_version=WRITING_STATE_POLICY_VERSION,
                    last_evidence_id=last_evidence_id,
                    revision=revision,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.estimated_band = computed.estimated_band
                row.evidence_count = computed.evidence_count
                row.last_evidence_id = last_evidence_id
                row.revision = revision
                row.updated_at = now
            materialized[skill] = LearnerSkillStateSchema(
                learner_id=learner_id,
                skill=skill,
                estimated_band=computed.estimated_band,
                evidence_count=computed.evidence_count,
                last_evidence_id=last_evidence_id,
                state_policy_version=WRITING_STATE_POLICY_VERSION,
                revision=revision,
                updated_at=now,
            )

        state_set = LearnerSkillStateSet(**materialized)
        decision = plan_practice(
            learner_target_band=BandScore(value=learner.writing_target_band),
            states=state_set,
        )
        recommendation = PracticeRecommendation(
            learning_update_id=learning_update.id,
            learner_id=learner_id,
            decision_type=decision.decision_type.value,
            target_skill=decision.target_skill,
            learner_target_band=(
                decision.learner_target_band.value
                if decision.learner_target_band is not None
                else None
            ),
            current_estimate=decision.current_estimate,
            reason_codes=[code.value for code in decision.reason_codes],
            planner_version=decision.planner_version,
            state_snapshot=decision.state_snapshot.model_dump(mode="json"),
        )
        session.add(recommendation)

        session.commit()
        return AppliedLearningResult(
            learning_update_id=learning_update.id,
            recommendation=decision,
            reused=False,
        )
    except IntegrityError:
        # A concurrent duplicate application hit a uniqueness constraint; the
        # transaction is rolled back. Resolve to idempotent replay or an
        # explicit cross-owner conflict based on persisted truth.
        session.rollback()
        return _resolve_existing(
            session,
            learner_id=learner_id,
            writing_evaluation_id=writing_evaluation_id,
        )
    except BaseException:
        session.rollback()
        raise
