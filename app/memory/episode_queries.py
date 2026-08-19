"""Read-only L0 episode queries (P6-04).

L0 is the existing normalized PostgreSQL persistence; this layer only SELECTs
and projects it. It lists learner-owned ``LearningUpdate`` episodes in the
frozen deterministic order and reconstructs one full episode with complete
provenance (update, evaluation, attempt, four evidence rows, recommendation,
optional linked practice). No mutation, no provider call, no duplicate
persistence.

Episode types are derived deterministically: ``targeted_practice`` iff exactly
one ``WritingPractice`` references the episode's evaluation attempt
(``writing_practices.attempt_id`` is UNIQUE), otherwise ``initial_writing``.
``occurred_at`` is exactly ``LearningUpdate.created_at``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.learner.writing_policy import WRITING_SKILLS
from app.memory.errors import (
    EpisodeNotFoundError,
    MemoryInvariantError,
    MemoryPersistenceError,
)
from app.models.learning import (
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
)
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.common import BandScore
from app.schemas.learner import (
    LearnerSkillStateSet,
    LearningEvidence as LearningEvidenceSchema,
    LearningUpdate as LearningUpdateSchema,
)
from app.schemas.memory import (
    EpisodeSkillObservation,
    EpisodeSkillObservationSet,
    LearningEpisodeDetail,
    LearningEpisodeSummary,
    WritingAttemptView,
)
from app.schemas.planning import (
    DecisionType,
    PlannerReasonCode,
    PracticeRecommendationDecision,
)
from app.schemas.practice import (
    PracticeLifecycleState,
    PracticeResponse,
)
from app.schemas.writing import (
    CriterionEvaluation,
    EvaluationMetadata,
    WritingCriteria,
    WritingEvaluationResponse,
    WritingEvaluationResult,
)


def reconstruct_decision(row: PracticeRecommendation) -> PracticeRecommendationDecision:
    """Rebuild the full persisted planner decision from its row."""
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


def practice_response(row: WritingPractice) -> PracticeResponse:
    """Map one persisted practice row to its public read representation."""
    return PracticeResponse(
        id=row.id,
        learner_id=row.learner_id,
        recommendation_id=row.recommendation_id,
        target_skill=row.target_skill,
        question=row.question,
        focus_objective=row.focus_objective,
        instructions=list(row.instructions),
        checkpoints=list(row.checkpoints),
        practice_type=row.practice_type,
        generator_policy_version=row.generator_policy_version,
        provider=row.provider,
        model=row.model,
        prompt_version=row.prompt_version,
        thinking_mode=row.thinking_mode,
        lifecycle_state=PracticeLifecycleState(row.lifecycle_state),
        attempt_id=row.attempt_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def evaluation_result_from_row(
    evaluation: WritingEvaluation,
    attempt: WritingAttempt,
) -> WritingEvaluationResult:
    """Reconstruct the persisted evaluation result (bands + criteria feedback)."""
    criteria_feedback: dict[str, dict[str, object]] = evaluation.criteria_feedback
    criteria: dict[str, CriterionEvaluation] = {}
    for skill in WRITING_SKILLS:
        raw = criteria_feedback.get(skill)
        if raw is None:
            raise MemoryInvariantError(
                f"evaluation {evaluation.id} is missing criteria feedback for {skill!r}"
            )
        criteria[skill] = CriterionEvaluation(
            band=BandScore(value=getattr(evaluation, f"{skill}_band")),
            evidence=list(raw["evidence"]),
            feedback=raw["feedback"],
        )
    return WritingEvaluationResult(
        criteria=WritingCriteria(**criteria),
        strengths=list(evaluation.strengths),
        weaknesses=list(evaluation.weaknesses),
        error_tags=list(evaluation.error_tags),
        recommended_skills=list(evaluation.recommended_skills),
        feedback=evaluation.feedback,
        metadata=EvaluationMetadata(
            provider=evaluation.provider,
            model=evaluation.model,
            prompt_version=evaluation.prompt_version,
            rubric_version=evaluation.rubric_version,
            scoring_policy_version=evaluation.scoring_policy_version,
            thinking_mode=evaluation.thinking_mode,
        ),
        word_count=attempt.word_count,
    )


def _observation_from_evidence(row: LearningEvidence) -> EpisodeSkillObservation:
    return EpisodeSkillObservation(
        skill=row.skill,
        observed_band=BandScore(value=row.observed_band),
        learning_evidence_id=row.id,
        source_attempt_id=row.source_attempt_id,
        source_created_at=row.source_created_at,
    )


def _episode_join_stmt(*, learner_id: int, episode_id: int | None = None):
    stmt = (
        select(
            LearningUpdate,
            WritingEvaluation.id.label("writing_evaluation_id"),
            WritingAttempt.id.label("attempt_id"),
            PracticeRecommendation.id.label("recommendation_id"),
            PracticeRecommendation.decision_type.label("recommendation_decision_type"),
            PracticeRecommendation.target_skill.label("recommendation_target_skill"),
            PracticeRecommendation.reason_codes.label("recommendation_reason_codes"),
            PracticeRecommendation.planner_version.label("recommendation_planner_version"),
            WritingPractice.id.label("writing_practice_id"),
            WritingPractice.target_skill.label("practice_target_skill"),
        )
        .join(
            WritingEvaluation,
            WritingEvaluation.id == LearningUpdate.writing_evaluation_id,
        )
        .join(WritingAttempt, WritingAttempt.id == WritingEvaluation.attempt_id)
        .join(
            PracticeRecommendation,
            PracticeRecommendation.learning_update_id == LearningUpdate.id,
        )
        .outerjoin(WritingPractice, WritingPractice.attempt_id == WritingAttempt.id)
        .where(LearningUpdate.learner_id == learner_id)
    )
    if episode_id is not None:
        stmt = stmt.where(LearningUpdate.id == episode_id)
    return stmt.order_by(LearningUpdate.created_at.desc(), LearningUpdate.id.desc())


def _summary_from_row(row, evidence_by_episode: dict[int, dict[str, LearningEvidence]]) -> LearningEpisodeSummary:
    update: LearningUpdate = row[0]
    evidence = evidence_by_episode.get(update.id)
    if evidence is None:
        raise MemoryInvariantError(f"episode {update.id} has no persisted evidence")
    observations: dict[str, EpisodeSkillObservation] = {}
    for skill in WRITING_SKILLS:
        item = evidence.get(skill)
        if item is None:
            raise MemoryInvariantError(
                f"episode {update.id} is missing canonical evidence for {skill!r}"
            )
        observations[skill] = _observation_from_evidence(item)
    return LearningEpisodeSummary(
        episode_id=update.id,
        episode_type="targeted_practice" if row.writing_practice_id is not None else "initial_writing",
        occurred_at=update.created_at,
        writing_evaluation_id=row.writing_evaluation_id,
        attempt_id=row.attempt_id,
        writing_practice_id=row.writing_practice_id,
        practice_target_skill=row.practice_target_skill,
        recommendation_id=row.recommendation_id,
        recommendation_decision_type=row.recommendation_decision_type,
        recommendation_target_skill=row.recommendation_target_skill,
        recommendation_reason_codes=list(row.recommendation_reason_codes),
        planner_version=row.recommendation_planner_version,
        skill_observations=EpisodeSkillObservationSet(**observations),
    )


def _evidence_by_episode(
    session: Session,
    episode_ids: list[int],
) -> dict[int, dict[str, LearningEvidence]]:
    if not episode_ids:
        return {}
    rows = session.scalars(
        select(LearningEvidence).where(
            LearningEvidence.learning_update_id.in_(episode_ids)
        )
    ).all()
    grouped: dict[int, dict[str, LearningEvidence]] = {}
    for row in rows:
        grouped.setdefault(row.learning_update_id, {})[row.skill] = row
    return grouped


def list_learner_episodes(
    session: Session,
    *,
    learner_id: int,
) -> list[LearningEpisodeSummary]:
    """List learner-owned L0 episodes in frozen order (created_at DESC, id DESC)."""
    try:
        rows = session.execute(_episode_join_stmt(learner_id=learner_id)).all()
        evidence = _evidence_by_episode(session, [row[0].id for row in rows])
        return [_summary_from_row(row, evidence) for row in rows]
    except (EpisodeNotFoundError, MemoryInvariantError):
        raise
    except SQLAlchemyError as error:
        raise MemoryPersistenceError("learning memory read failed") from error


def get_learner_episode(
    session: Session,
    *,
    learner_id: int,
    episode_id: int,
) -> LearningEpisodeDetail:
    """Reconstruct one learner-owned episode with full provenance."""
    try:
        row = session.execute(
            _episode_join_stmt(learner_id=learner_id, episode_id=episode_id)
        ).first()
        if row is None:
            raise EpisodeNotFoundError(f"episode {episode_id} was not found")
        update: LearningUpdate = row[0]
        evidence = _evidence_by_episode(session, [update.id]).get(update.id, {})
        summary = _summary_from_row(row, {update.id: evidence})

        evaluation = session.get(WritingEvaluation, update.writing_evaluation_id)
        attempt = session.get(WritingAttempt, row.attempt_id)
        if evaluation is None or attempt is None:
            raise MemoryInvariantError(
                f"episode {update.id} has an incomplete evaluation/attempt chain"
            )
        evaluation_rows = session.scalars(
            select(LearningEvidence).where(
                LearningEvidence.learning_update_id == update.id
            )
        ).all()
        if len(evaluation_rows) != 4:
            raise MemoryInvariantError(
                f"episode {update.id} does not have exactly four evidence rows"
            )
        evidence_schemas = [
            LearningEvidenceSchema(
                id=item.id,
                learning_update_id=item.learning_update_id,
                learner_id=item.learner_id,
                writing_evaluation_id=item.writing_evaluation_id,
                skill=item.skill,
                observed_band=BandScore(value=item.observed_band),
                source_created_at=item.source_created_at,
                source_attempt_id=item.source_attempt_id,
                provenance=EvaluationMetadata(
                    provider=item.provider,
                    model=item.model,
                    prompt_version=item.prompt_version,
                    rubric_version=item.rubric_version,
                    scoring_policy_version=item.scoring_policy_version,
                    thinking_mode=item.thinking_mode,
                ),
                created_at=item.created_at,
            )
            for item in sorted(evaluation_rows, key=lambda r: (r.source_created_at, r.source_attempt_id))
        ]
        recommendation = session.scalar(
            select(PracticeRecommendation).where(
                PracticeRecommendation.learning_update_id == update.id
            )
        )
        if recommendation is None:
            raise MemoryInvariantError(f"episode {update.id} has no recommendation")
        practice = None
        if row.writing_practice_id is not None:
            practice_row = session.get(WritingPractice, row.writing_practice_id)
            if practice_row is None:
                raise MemoryInvariantError(
                    f"episode {update.id} has an unresolved practice link"
                )
            practice = practice_response(practice_row)

        return LearningEpisodeDetail(
            episode=summary,
            learning_update=LearningUpdateSchema(
                id=update.id,
                learner_id=update.learner_id,
                writing_evaluation_id=update.writing_evaluation_id,
                skill_taxonomy_version=update.skill_taxonomy_version,
                state_policy_version=update.state_policy_version,
                planner_version=update.planner_version,
                created_at=update.created_at,
            ),
            attempt=WritingAttemptView(
                attempt_id=attempt.id,
                question=attempt.question,
                essay=attempt.essay,
                word_count=attempt.word_count,
                created_at=attempt.created_at,
            ),
            evaluation=WritingEvaluationResponse(
                attempt_id=attempt.id,
                evaluation_id=evaluation.id,
                evaluation=evaluation_result_from_row(evaluation, attempt),
            ),
            evidence=evidence_schemas,
            recommendation=reconstruct_decision(recommendation),
            practice=practice,
        )
    except (EpisodeNotFoundError, MemoryInvariantError):
        raise
    except SQLAlchemyError as error:
        raise MemoryPersistenceError("learning memory read failed") from error
