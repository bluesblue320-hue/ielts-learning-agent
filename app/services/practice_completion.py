"""P4-11 completion: apply one submitted practice evaluation and replan."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.practice import WritingPractice
from app.models.writing import WritingEvaluation
from app.schemas.practice import ClosedLoopResult, PracticeLifecycleState
from app.services.learning_application import (
    AppliedLearningResult,
    apply_writing_evaluation,
)


class PracticeCompletionError(Exception):
    """Base error for closed-loop completion outcomes."""


class PracticeCompletionNotFoundError(PracticeCompletionError):
    """The requested persisted practice does not exist."""


class PracticeCompletionOwnershipError(PracticeCompletionError):
    """The requested practice belongs to another learner."""


class PracticeNotSubmittedError(PracticeCompletionError):
    """A practice cannot be completed before atomic submission finalization."""


class PracticeCompletionPersistenceError(PracticeCompletionError):
    """The submitted practice trace is unexpectedly incomplete."""


class PracticeCompletionService:
    """Reuse Phase 3 apply idempotency; never generate another practice."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def complete(self, *, learner_id: int, practice_id: int) -> ClosedLoopResult:
        try:
            practice = self._session.scalar(
                select(WritingPractice).where(WritingPractice.id == practice_id)
            )
            if practice is None:
                raise PracticeCompletionNotFoundError("writing practice was not found")
            if practice.learner_id != learner_id:
                raise PracticeCompletionOwnershipError(
                    "writing practice belongs to another learner"
                )
            if practice.lifecycle_state != PracticeLifecycleState.SUBMITTED.value:
                raise PracticeNotSubmittedError("writing practice has not been submitted")
            if practice.attempt_id is None:
                raise PracticeCompletionPersistenceError(
                    "submitted practice has no writing attempt"
                )
            evaluation = self._session.scalar(
                select(WritingEvaluation).where(
                    WritingEvaluation.attempt_id == practice.attempt_id
                )
            )
            if evaluation is None:
                raise PracticeCompletionPersistenceError(
                    "submitted practice has no writing evaluation"
                )
            attempt_id = practice.attempt_id
            evaluation_id = evaluation.id
            self._session.rollback()
        except PracticeCompletionError:
            self._session.rollback()
            raise
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeCompletionPersistenceError(
                "writing practice completion persistence failure"
            ) from error

        applied: AppliedLearningResult = apply_writing_evaluation(
            self._session,
            learner_id=learner_id,
            writing_evaluation_id=evaluation_id,
        )
        return ClosedLoopResult(
            practice_id=practice_id,
            attempt_id=attempt_id,
            evaluation_id=evaluation_id,
            learning_update_id=applied.learning_update_id,
            next_recommendation_id=applied.recommendation_id,
            next_recommendation=applied.recommendation,
        )
