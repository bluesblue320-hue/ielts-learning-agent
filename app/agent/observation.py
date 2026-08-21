"""Provider-free, acceptance-order-authoritative Agent observation."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.learner.planning_reconstruction import reconstruct_persisted_decision
from app.memory.episode_queries import practice_response
from app.memory.errors import MemoryInvariantError
from app.models.learning import Learner, LearningUpdate, PracticeRecommendation
from app.models.practice import WritingPractice
from app.models.writing import WritingEvaluation
from app.schemas.agent import AgentObservation, NoPracticeReason, ObservationKind
from app.schemas.planning import DecisionType, PublicPracticeRecommendationDecision
from app.schemas.practice import PracticeLifecycleState, PracticeResponse
from app.services.learning_application import LearnerNotFoundError


class AgentObservationPersistenceError(Exception):
    """Persisted state could not be read for an Agent observation."""


@dataclass(frozen=True)
class AgentObservedState:
    """Public-safe observation plus the minimal private execution anchors."""

    observation: AgentObservation
    latest_learning_update_id: int | None
    recommendation_id: int | None
    practice_id: int | None
    recommendation: PublicPracticeRecommendationDecision | None
    practice: PracticeResponse | None
    practice_lifecycle_state: PracticeLifecycleState | None
    practice_submission_fingerprint: str | None
    practice_evaluation_id: int | None
    practice_completion_applied: bool


def observe_agent_state(session: Session, *, learner_id: int) -> AgentObservedState:
    """Classify the latest accepted Writing state without provider work.

    This intentionally differs from frozen ``writing-context-v1``: the Agent
    uses accepted-update order (``LearningUpdate.id DESC``), not timestamps.
    """

    try:
        if session.get(Learner, learner_id) is None:
            raise LearnerNotFoundError(f"learner {learner_id} not found")

        latest = session.scalar(
            select(LearningUpdate)
            .where(LearningUpdate.learner_id == learner_id)
            .order_by(LearningUpdate.id.desc())
            .limit(1)
        )
        if latest is None:
            return AgentObservedState(
                observation=AgentObservation(kind=ObservationKind.NEEDS_INITIAL_WRITING),
                latest_learning_update_id=None,
                recommendation_id=None,
                practice_id=None,
                recommendation=None,
                practice=None,
                practice_lifecycle_state=None,
                practice_submission_fingerprint=None,
                practice_evaluation_id=None,
                practice_completion_applied=False,
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
        public_recommendation = reconstruct_persisted_decision(recommendation)

        if recommendation.decision_type == DecisionType.NO_PRACTICE.value:
            return AgentObservedState(
                observation=AgentObservation(
                    kind=ObservationKind.NO_PRACTICE,
                    no_practice_reason_codes=[
                        NoPracticeReason(reason) for reason in recommendation.reason_codes
                    ],
                ),
                latest_learning_update_id=latest.id,
                recommendation_id=recommendation.id,
                practice_id=None,
                recommendation=public_recommendation,
                practice=None,
                practice_lifecycle_state=None,
                practice_submission_fingerprint=None,
                practice_evaluation_id=None,
                practice_completion_applied=False,
            )

        practice = session.scalar(
            select(WritingPractice).where(
                WritingPractice.recommendation_id == recommendation.id
            )
        )
        if practice is None:
            return AgentObservedState(
                observation=AgentObservation(kind=ObservationKind.NEEDS_GENERATION),
                latest_learning_update_id=latest.id,
                recommendation_id=recommendation.id,
                practice_id=None,
                recommendation=public_recommendation,
                practice=None,
                practice_lifecycle_state=None,
                practice_submission_fingerprint=None,
                practice_evaluation_id=None,
                practice_completion_applied=False,
            )

        public_practice = practice_response(practice)
        lifecycle = PracticeLifecycleState(practice.lifecycle_state)
        if lifecycle == PracticeLifecycleState.GENERATED:
            kind = ObservationKind.NEEDS_PRACTICE_SUBMISSION
            evaluation_id = None
            completion_applied = False
        elif lifecycle == PracticeLifecycleState.SUBMISSION_IN_PROGRESS:
            kind = ObservationKind.AWAIT_SUBMISSION
            evaluation_id = None
            completion_applied = False
        elif lifecycle == PracticeLifecycleState.SUBMITTED:
            evaluation = session.scalar(
                select(WritingEvaluation).where(WritingEvaluation.attempt_id == practice.attempt_id)
            )
            if evaluation is None:
                raise MemoryInvariantError(
                    f"submitted practice {practice.id} has no linked evaluation"
                )
            evaluation_id = evaluation.id
            completion_applied = (
                session.scalar(
                    select(LearningUpdate.id).where(
                        LearningUpdate.writing_evaluation_id == evaluation.id
                    )
                )
                is not None
            )
            if completion_applied:
                raise MemoryInvariantError(
                    "current recommendation's practice is already applied; "
                    "the Agent must re-observe the newer accepted update"
                )
            kind = ObservationKind.NEEDS_COMPLETION
        else:  # pragma: no cover - lifecycle is database constrained
            raise MemoryInvariantError(f"practice {practice.id} has an unknown lifecycle state")

        return AgentObservedState(
            observation=AgentObservation(kind=kind),
            latest_learning_update_id=latest.id,
            recommendation_id=recommendation.id,
            practice_id=practice.id,
            recommendation=public_recommendation,
            practice=public_practice,
            practice_lifecycle_state=lifecycle,
            practice_submission_fingerprint=practice.submission_fingerprint,
            practice_evaluation_id=evaluation_id,
            practice_completion_applied=completion_applied,
        )
    except (LearnerNotFoundError, MemoryInvariantError):
        raise
    except SQLAlchemyError as error:
        raise AgentObservationPersistenceError("agent observation read failed") from error
