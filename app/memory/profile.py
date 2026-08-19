"""L3 learner memory profile read model (P6-07).

Assembles the ``GET /learners/{learner_id}/writing/progress`` response: the L2
per-skill longitudinal patterns plus the L3 profile section (current target
from ``Learner``, current four-skill state READ from ``LearnerSkillState``,
and per-skill summaries). The authoritative state engine is never recomputed;
``LearnerSkillState`` remains the source of current state. Nothing is
persisted, and no qualitative labels are generated.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.learner.writing_policy import (
    WRITING_SKILLS,
    WRITING_STATE_POLICY_VERSION,
)
from app.memory.errors import MemoryPersistenceError
from app.memory.episode_queries import list_learner_episodes
from app.memory.pattern_engine import (
    SkillObservationPoint,
    compute_persistent_gap,
    compute_trend,
    latest_observation_time,
    recent_observation_count,
    recent_practice_count_for_skill,
    recent_practice_source_episode_ids,
    trend_source_episode_ids,
    trend_source_observation_ids,
)
from app.memory.progress_policy import PROGRESS_POLICY_VERSION
from app.models.learning import (
    Learner,
    LearnerSkillState,
    LearningEvidence,
)
from app.schemas.common import BandScore
from app.schemas.learner import (
    LearnerSkillState as LearnerSkillStateSchema,
    LearnerSkillStateSet,
)
from app.schemas.memory import (
    MEMORY_VERSION,
    SkillProgress,
    SkillProgressSet,
    WritingProgressResponse,
)
from app.services.learning_application import LearnerNotFoundError


def _evidence_points(
    rows: list[LearningEvidence],
    *,
    skill: str,
) -> list[SkillObservationPoint]:
    """Canonically ordered observation points for one skill."""
    ordered = sorted(
        (row for row in rows if row.skill == skill),
        key=lambda row: (row.source_created_at, row.source_attempt_id),
    )
    return [
        SkillObservationPoint(
            learning_evidence_id=row.id,
            learning_update_id=row.learning_update_id,
            observed_band=Decimal(row.observed_band),
            source_created_at=row.source_created_at,
        )
        for row in ordered
    ]


def _current_state(
    rows: dict[str, LearnerSkillState],
    *,
    learner_id: int,
    learner_created_at,
) -> LearnerSkillStateSet:
    """Read the current four-skill state (never recomputed)."""
    states: dict[str, LearnerSkillStateSchema] = {}
    for skill in WRITING_SKILLS:
        row = rows.get(skill)
        if row is None:
            states[skill] = LearnerSkillStateSchema(
                learner_id=learner_id,
                skill=skill,
                estimated_band=None,
                evidence_count=0,
                last_evidence_id=None,
                state_policy_version=WRITING_STATE_POLICY_VERSION,
                revision=0,
                updated_at=learner_created_at,
            )
        else:
            states[skill] = LearnerSkillStateSchema(
                learner_id=row.learner_id,
                skill=row.skill,
                estimated_band=row.estimated_band,
                evidence_count=row.evidence_count,
                last_evidence_id=row.last_evidence_id,
                state_policy_version=row.state_policy_version,
                revision=row.revision,
                updated_at=row.updated_at,
            )
    return LearnerSkillStateSet(**states)


def build_learner_progress(
    session: Session,
    *,
    learner_id: int,
) -> WritingProgressResponse:
    """Assemble the L3 profile + L2 patterns for one learner."""
    try:
        learner = session.get(Learner, learner_id)
        if learner is None:
            raise LearnerNotFoundError(f"learner {learner_id} not found")

        state_rows = {
            row.skill: row
            for row in session.scalars(
                select(LearnerSkillState).where(
                    LearnerSkillState.learner_id == learner_id
                )
            ).all()
        }
        evidence_rows = list(
            session.scalars(
                select(LearningEvidence).where(
                    LearningEvidence.learner_id == learner_id
                )
            ).all()
        )
        episodes = list_learner_episodes(session, learner_id=learner_id)

        current_target = Decimal(learner.writing_target_band)
        current_state = _current_state(
            state_rows,
            learner_id=learner_id,
            learner_created_at=learner.created_at,
        )
        skills: dict[str, SkillProgress] = {}
        for skill in WRITING_SKILLS:
            points = _evidence_points(evidence_rows, skill=skill)
            state = getattr(current_state, skill)
            trend = compute_trend(points)
            gap = compute_persistent_gap(
                points,
                current_target_band=current_target,
            )
            skills[skill] = SkillProgress(
                learner_id=learner_id,
                skill=skill,
                policy_version=PROGRESS_POLICY_VERSION,
                current_estimate=state.estimated_band,
                evidence_count=state.evidence_count,
                trend=trend.trend,
                persistent_gap=gap.persistent_gap,
                persistent_gap_status=gap.status,
                recent_observation_count=recent_observation_count(points),
                recent_practice_count=recent_practice_count_for_skill(
                    episodes,
                    skill=skill,
                ),
                latest_observation_time=latest_observation_time(points),
                last_episode_id=episodes[0].episode_id if episodes else None,
                source_observation_ids=trend_source_observation_ids(points),
                source_episode_ids=trend_source_episode_ids(points),
                recent_practice_source_episode_ids=recent_practice_source_episode_ids(
                    episodes
                ),
            )
        return WritingProgressResponse(
            learner_id=learner_id,
            current_writing_target_band=BandScore(value=learner.writing_target_band),
            current_state=current_state,
            skills=SkillProgressSet(**skills),
            memory_version=MEMORY_VERSION,
            progress_version=PROGRESS_POLICY_VERSION,
        )
    except (MemoryPersistenceError, LearnerNotFoundError):
        raise
    except SQLAlchemyError as error:
        raise MemoryPersistenceError("learning memory read failed") from error
