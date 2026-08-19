"""Server-authoritative resume context (P6-08).

Implements exactly the frozen resume contract from
``docs/WRITING_MEMORY_POLICY.md`` section 1.17:

- current recommendation = the ``PracticeRecommendation`` owned by the
  learner's latest ``LearningUpdate`` (``created_at DESC, id DESC``);
- relevant practice = ONLY the ``WritingPractice`` linked to that current
  recommendation (``writing_practices.recommendation_id`` is UNIQUE, so at
  most one); older unfinished practices never override it;
- the resume action is a single non-recursive branch over persisted
  learner-owned data; the endpoint never generates a practice;
- an unapplied initial evaluation is NOT learner-owned and cannot be recovered
  from ``learner_id`` alone; with no ``LearningUpdate`` the action is
  ``initial_writing``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.memory.errors import MemoryInvariantError, MemoryPersistenceError
from app.memory.episode_queries import practice_response, reconstruct_decision
from app.memory.profile import _current_state
from app.models.learning import (
    Learner,
    LearnerSkillState,
    LearningUpdate,
    PracticeRecommendation,
)
from app.models.practice import WritingPractice
from app.models.writing import WritingEvaluation
from app.schemas.memory import WritingContextResponse
from app.schemas.practice import PracticeLifecycleState
from app.services.learning_application import LearnerNotFoundError


def build_learner_context(
    session: Session,
    *,
    learner_id: int,
) -> WritingContextResponse:
    """Return the deterministic server-authoritative resume context."""
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
        current_state = _current_state(
            state_rows,
            learner_id=learner_id,
            learner_created_at=learner.created_at,
        )

        latest = session.scalar(
            select(LearningUpdate)
            .where(LearningUpdate.learner_id == learner_id)
            .order_by(LearningUpdate.created_at.desc(), LearningUpdate.id.desc())
            .limit(1)
        )
        if latest is None:
            # Resume v1 limitation: with no learner-owned LearningUpdate the
            # action is initial_writing (an unapplied initial evaluation is
            # not discoverable from learner_id alone).
            return WritingContextResponse(
                learner_id=learner_id,
                resume_action="initial_writing",
                has_learner_owned_episodes=False,
                latest_learning_update_id=None,
                current_recommendation_id=None,
                current_recommendation=None,
                relevant_practice=None,
                current_state=current_state,
            )

        recommendation = session.scalar(
            select(PracticeRecommendation).where(
                PracticeRecommendation.learning_update_id == latest.id
            )
        )
        if recommendation is None:
            raise MemoryInvariantError(
                f"learning update {latest.id} has no persisted recommendation"
            )
        decision = reconstruct_decision(recommendation)

        if recommendation.decision_type == "no_practice":
            return WritingContextResponse(
                learner_id=learner_id,
                resume_action="no_action",
                has_learner_owned_episodes=True,
                latest_learning_update_id=latest.id,
                current_recommendation_id=recommendation.id,
                current_recommendation=decision,
                relevant_practice=None,
                current_state=current_state,
            )

        practice = session.scalar(
            select(WritingPractice).where(
                WritingPractice.recommendation_id == recommendation.id
            )
        )
        if practice is None:
            return WritingContextResponse(
                learner_id=learner_id,
                resume_action="generate_practice",
                has_learner_owned_episodes=True,
                latest_learning_update_id=latest.id,
                current_recommendation_id=recommendation.id,
                current_recommendation=decision,
                relevant_practice=None,
                current_state=current_state,
            )

        relevant = practice_response(practice)
        if practice.lifecycle_state == PracticeLifecycleState.GENERATED.value:
            resume_action = "submit_practice"
        elif practice.lifecycle_state == PracticeLifecycleState.SUBMISSION_IN_PROGRESS.value:
            resume_action = "await_submission"
        elif practice.lifecycle_state == PracticeLifecycleState.SUBMITTED.value:
            evaluation = session.scalar(
                select(WritingEvaluation).where(
                    WritingEvaluation.attempt_id == practice.attempt_id
                )
            )
            if evaluation is None:
                raise MemoryInvariantError(
                    f"submitted practice {practice.id} has no linked evaluation"
                )
            applied = session.scalar(
                select(LearningUpdate).where(
                    LearningUpdate.writing_evaluation_id == evaluation.id
                )
            )
            if applied is None:
                resume_action = "complete_practice"
            else:
                # Unreachable for the current recommendation: applying the
                # linked evaluation created a NEW latest LearningUpdate /
                # recommendation, so context is resolved from that single
                # latest query (already performed above), never by recursing
                # through this older recommendation.
                raise MemoryInvariantError(
                    "current recommendation's practice is already applied; "
                    "the resume context must be resolved from the new latest "
                    "LearningUpdate"
                )
        else:  # pragma: no cover - lifecycle is constrained by the DB check
            raise MemoryInvariantError(
                f"practice {practice.id} has an unknown lifecycle state"
            )

        return WritingContextResponse(
            learner_id=learner_id,
            resume_action=resume_action,
            has_learner_owned_episodes=True,
            latest_learning_update_id=latest.id,
            current_recommendation_id=recommendation.id,
            current_recommendation=decision,
            relevant_practice=relevant,
            current_state=current_state,
        )
    except (LearnerNotFoundError, MemoryInvariantError):
        raise
    except SQLAlchemyError as error:
        raise MemoryPersistenceError("learning memory read failed") from error
