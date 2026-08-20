"""Decision-time Memory context for a Phase 7 exact maximum-gap tie.

This module owns a deliberately small planner projection. It reuses Phase 6
observation chronology for trend and persistent gap, while defining its own
accepted-``LearningUpdate.id`` practice-recency window. It never calls the L0
episode read API and does not depend on a persisted recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.learner.memory_planning_policy import (
    MEMORY_CONTEXT_VERSION,
    PLANNING_RECENT_PRACTICE_WINDOW,
)
from app.learner.writing_policy import WRITING_SKILLS
from app.memory.pattern_engine import (
    SkillObservationPoint,
    compute_persistent_gap,
    compute_trend,
    trend_source_episode_ids,
    trend_source_observation_ids,
)
from app.memory.progress_policy import PROGRESS_POLICY_VERSION
from app.models.learning import LearningEvidence, LearningUpdate
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.memory import MEMORY_VERSION
from app.schemas.planning import (
    MemoryAwarePlanningContext,
    MemoryAwarePlanningSkillContext,
    MemoryAwarePlanningSkillContextSet,
)


class PlanningContextError(Exception):
    """Base exception for a decision-time memory-context build."""


class PlanningContextOwnerNotFoundError(PlanningContextError):
    """The bounded owner update is absent or belongs to another learner."""


class PlanningContextPersistenceError(PlanningContextError):
    """A database failure prevented exact-tie context construction."""


@dataclass(frozen=True)
class PlanningPracticeEpisode:
    """The only accepted-update projection needed for planner recency."""

    learning_update_id: int
    practice_target_skill: str | None


def _canonical_points(
    evidence_rows: list[LearningEvidence],
    *,
    skill: str,
) -> list[SkillObservationPoint]:
    """Return one skill's frozen Phase 6 canonical observation sequence."""

    rows = sorted(
        (row for row in evidence_rows if row.skill == skill),
        key=lambda row: (row.source_created_at, row.source_attempt_id),
    )
    return [
        SkillObservationPoint(
            learning_evidence_id=row.id,
            learning_update_id=row.learning_update_id,
            observed_band=Decimal(row.observed_band),
            source_created_at=row.source_created_at,
        )
        for row in rows
    ]


def _planning_practice_episodes(
    session: Session,
    *,
    learner_id: int,
    owner_learning_update_id: int,
) -> list[PlanningPracticeEpisode]:
    """Read the bounded accepted-update recency window in ``id DESC`` order.

    The joins reach only the persisted practice that supplied the completed
    attempt's actual target skill. There is intentionally no recommendation or
    L0 episode dependency, so a just-flushed current update participates before
    its new recommendation exists.
    """

    rows = session.execute(
        select(
            LearningUpdate.id,
            WritingPractice.target_skill,
        )
        .join(
            WritingEvaluation,
            WritingEvaluation.id == LearningUpdate.writing_evaluation_id,
        )
        .join(WritingAttempt, WritingAttempt.id == WritingEvaluation.attempt_id)
        .outerjoin(WritingPractice, WritingPractice.attempt_id == WritingAttempt.id)
        .where(
            LearningUpdate.learner_id == learner_id,
            LearningUpdate.id <= owner_learning_update_id,
        )
        .order_by(LearningUpdate.id.desc())
        .limit(PLANNING_RECENT_PRACTICE_WINDOW)
    ).all()
    return [
        PlanningPracticeEpisode(
            learning_update_id=row.id,
            practice_target_skill=row.target_skill,
        )
        for row in rows
    ]


def _ensure_owned_update(
    session: Session,
    *,
    learner_id: int,
    owner_learning_update_id: int,
) -> None:
    """Ensure the historical reconstruction owner is learner-owned."""

    owner_id = session.scalar(
        select(LearningUpdate.id).where(
            LearningUpdate.id == owner_learning_update_id,
            LearningUpdate.learner_id == learner_id,
        )
    )
    if owner_id is None:
        raise PlanningContextOwnerNotFoundError(
            f"learning update {owner_learning_update_id} was not found for learner"
        )


def build_memory_aware_planning_context(
    session: Session,
    *,
    learner_id: int,
    current_target_band: Decimal,
    owner_learning_update_id: int,
) -> MemoryAwarePlanningContext:
    """Build exact-tie input facts bounded by an accepted owner update.

    Callers must invoke this only after deterministic base selection has found
    an exact maximum-gap tie. ``owner_learning_update_id`` is the current
    just-flushed update at apply time and is also the historical reconstruction
    boundary: all queried rows have the same learner and ``id <= owner``.
    """

    try:
        _ensure_owned_update(
            session,
            learner_id=learner_id,
            owner_learning_update_id=owner_learning_update_id,
        )
        evidence_rows = list(
            session.scalars(
                select(LearningEvidence).where(
                    LearningEvidence.learner_id == learner_id,
                    LearningEvidence.learning_update_id <= owner_learning_update_id,
                )
            ).all()
        )
        practice_episodes = _planning_practice_episodes(
            session,
            learner_id=learner_id,
            owner_learning_update_id=owner_learning_update_id,
        )
        window_ids = [episode.learning_update_id for episode in practice_episodes]
        if not window_ids:
            raise PlanningContextOwnerNotFoundError(
                "owner update must appear in the accepted-update recency window"
            )
        if window_ids[0] != owner_learning_update_id:
            raise PlanningContextOwnerNotFoundError(
                "owner update must be first in its bounded accepted-update window"
            )

        contexts: dict[str, MemoryAwarePlanningSkillContext] = {}
        for skill in WRITING_SKILLS:
            points = _canonical_points(evidence_rows, skill=skill)
            trend = compute_trend(points)
            persistent_gap = compute_persistent_gap(
                points,
                current_target_band=current_target_band,
            )
            contexts[skill] = MemoryAwarePlanningSkillContext(
                skill=skill,
                trend=trend.trend,
                persistent_gap=persistent_gap.persistent_gap,
                persistent_gap_status=persistent_gap.status,
                recent_practice_count=sum(
                    episode.practice_target_skill == skill
                    for episode in practice_episodes
                ),
                source_observation_ids=trend_source_observation_ids(points),
                source_episode_ids=trend_source_episode_ids(points),
                recent_practice_source_episode_ids=window_ids,
            )

        return MemoryAwarePlanningContext(
            memory_version=MEMORY_VERSION,
            progress_version=PROGRESS_POLICY_VERSION,
            memory_context_version=MEMORY_CONTEXT_VERSION,
            skills=MemoryAwarePlanningSkillContextSet(**contexts),
        )
    except PlanningContextError:
        raise
    except SQLAlchemyError as error:
        raise PlanningContextPersistenceError(
            "decision-time planning context query failed"
        ) from error
