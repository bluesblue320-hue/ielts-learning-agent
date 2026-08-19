"""L1 atom derivation (P6-05) — read-model projections over persisted rows.

Exactly four v1 atom kinds exist:

- ``skill_observation``: authoritative source is one ``LearningEvidence`` row;
- ``practice_completed``: a ``WritingPractice`` that is ``submitted`` AND whose
  linked evaluation has been applied (a ``LearningUpdate`` exists). Without the
  applied evaluation there is NO atom;
- ``target_snapshot``: the HISTORICAL episode target, sourced ONLY from
  ``PracticeRecommendation.learner_target_band``. The current
  ``Learner.writing_target_band`` is never substituted;
- ``recommendation_observation``: the full persisted planner decision.

Every atom exposes its authoritative source ids. No atom without a source may
be produced. Atoms are NOT persisted and carry no synthetic memory ids.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning import (
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
)
from app.models.practice import WritingPractice
from app.models.writing import WritingEvaluation
from app.schemas.common import BandScore
from app.schemas.memory import (
    PracticeCompletedAtom,
    RecommendationObservationAtom,
    SkillObservationAtom,
    TargetSnapshotAtom,
)
from app.schemas.planning import AnyPracticeRecommendationDecision
from app.schemas.practice import PracticeLifecycleState


def skill_observation_atom(row: LearningEvidence) -> SkillObservationAtom:
    """Project one persisted evidence row as a ``skill_observation`` atom."""
    return SkillObservationAtom(
        atom_kind="skill_observation",
        skill=row.skill,
        observed_band=BandScore(value=row.observed_band),
        learning_evidence_id=row.id,
        learning_update_id=row.learning_update_id,
        writing_evaluation_id=row.writing_evaluation_id,
        source_attempt_id=row.source_attempt_id,
        source_created_at=row.source_created_at,
    )


def derive_practice_completed(
    session: Session,
    *,
    practice: WritingPractice,
) -> PracticeCompletedAtom | None:
    """Derive a ``practice_completed`` atom or return None.

    Returns None when the practice is not ``submitted``, has no attempt link,
    has no linked evaluation, or its linked evaluation has NOT been applied.
    No atom means "not completed" in Phase 6 memory semantics.
    """
    if practice.lifecycle_state != PracticeLifecycleState.SUBMITTED.value:
        return None
    if practice.attempt_id is None:
        return None
    evaluation = session.scalar(
        select(WritingEvaluation).where(
            WritingEvaluation.attempt_id == practice.attempt_id
        )
    )
    if evaluation is None:
        return None
    update = session.scalar(
        select(LearningUpdate).where(
            LearningUpdate.writing_evaluation_id == evaluation.id
        )
    )
    if update is None:
        return None
    return PracticeCompletedAtom(
        atom_kind="practice_completed",
        skill=practice.target_skill,
        writing_practice_id=practice.id,
        learning_update_id=update.id,
        writing_evaluation_id=evaluation.id,
        attempt_id=practice.attempt_id,
        completed_at=update.created_at,
    )


def target_snapshot_atom(
    row: PracticeRecommendation,
) -> TargetSnapshotAtom | None:
    """Derive the HISTORICAL ``target_snapshot`` atom.

    Sourced only from ``PracticeRecommendation.learner_target_band``. A
    ``target_unset`` decision (null historical band) has no snapshot atom.
    """
    if row.learner_target_band is None:
        return None
    return TargetSnapshotAtom(
        atom_kind="target_snapshot",
        learning_update_id=row.learning_update_id,
        recommendation_id=row.id,
        historical_target_band=BandScore(value=Decimal(row.learner_target_band)),
    )


def recommendation_observation_atom(
    row: PracticeRecommendation,
    *,
    decision: AnyPracticeRecommendationDecision,
) -> RecommendationObservationAtom:
    """Project one persisted recommendation as an observation atom.

    ``decision`` is the reconstructed versioned public decision
    (see ``app.memory.episode_queries.reconstruct_decision``).
    """
    return RecommendationObservationAtom(
        atom_kind="recommendation_observation",
        learning_update_id=row.learning_update_id,
        recommendation_id=row.id,
        decision=decision,
    )
