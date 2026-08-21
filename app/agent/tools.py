"""Direct existing-service adapters for one deterministic Agent turn."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.learning import LearningUpdate
from app.models.practice import WritingPractice
from app.models.writing import WritingEvaluation
from app.schemas.practice import PracticeLifecycleState, PracticeSubmission
from app.services.practice_completion import (
    PracticeCompletionPersistenceError,
    PracticeCompletionService,
)
from app.services.practice_generation import AgentGenerationOutcome, PracticeGenerationService
from app.services.practice_submission import (
    PracticeNotFoundError,
    PracticeOwnershipError,
    PracticeSubmissionPersistenceError,
    PracticeSubmissionService,
    submission_fingerprint,
)
from app.services.writing_evaluation import WritingEvaluationService


@dataclass(frozen=True)
class SubmittedPracticeReplay:
    """Provider-free resolution for a non-current submitted practice retry."""

    matches: bool
    completion_applied: bool


class AgentTools:
    """Thin direct adapters; provider-backed services are created on demand."""

    def __init__(
        self,
        *,
        generation: PracticeGenerationService | None = None,
        submission: PracticeSubmissionService | None = None,
        completion: PracticeCompletionService | None = None,
        session: Session | None = None,
        generator_factory: Callable[[], object] | None = None,
        provider_factory: Callable[[], object] | None = None,
    ) -> None:
        self._generation = generation
        self._submission = submission
        self._completion = completion
        self._session = session
        self._generator_factory = generator_factory
        self._provider_factory = provider_factory

    def _generation_service(self) -> PracticeGenerationService:
        if self._generation is None:
            assert self._session is not None and self._generator_factory is not None
            self._generation = PracticeGenerationService(
                self._session, self._generator_factory()
            )
        return self._generation

    def _submission_service(self) -> PracticeSubmissionService:
        if self._submission is None:
            assert self._session is not None and self._provider_factory is not None
            self._submission = PracticeSubmissionService(
                self._session,
                lambda: WritingEvaluationService(self._provider_factory()),
            )
        return self._submission

    def _completion_service(self) -> PracticeCompletionService:
        if self._completion is None:
            assert self._session is not None
            self._completion = PracticeCompletionService(self._session)
        return self._completion

    def resolve_submitted_replay(
        self, *, learner_id: int, practice_id: int, essay: str
    ) -> SubmittedPracticeReplay | None:
        """Resolve only a historical submitted replay before it may be submitted.

        A non-current generated practice remains stale and is left for the pure
        selector to reject. This preflight intentionally exposes no data and
        does no provider work.
        """

        assert self._session is not None
        try:
            practice = self._session.scalar(
                select(WritingPractice).where(WritingPractice.id == practice_id)
            )
            if practice is None:
                raise PracticeNotFoundError("writing practice was not found")
            if practice.learner_id != learner_id:
                raise PracticeOwnershipError("writing practice belongs to another learner")
            if practice.lifecycle_state != PracticeLifecycleState.SUBMITTED.value:
                return None
            fingerprint = submission_fingerprint(
                practice_id=practice.id,
                question=practice.question,
                essay=essay,
            )
            if practice.submission_fingerprint != fingerprint:
                return SubmittedPracticeReplay(matches=False, completion_applied=False)
            if practice.attempt_id is None:
                raise PracticeSubmissionPersistenceError(
                    "submitted practice has no writing attempt"
                )
            evaluation = self._session.scalar(
                select(WritingEvaluation).where(
                    WritingEvaluation.attempt_id == practice.attempt_id
                )
            )
            if evaluation is None:
                raise PracticeSubmissionPersistenceError(
                    "submitted practice has no evaluation"
                )
            return SubmittedPracticeReplay(
                matches=True,
                completion_applied=(
                    self._session.scalar(
                        select(LearningUpdate.id).where(
                            LearningUpdate.writing_evaluation_id == evaluation.id
                        )
                    )
                    is not None
                ),
            )
        except (PracticeNotFoundError, PracticeOwnershipError, PracticeSubmissionPersistenceError):
            raise
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeSubmissionPersistenceError(
                "submitted practice replay could not be resolved"
            ) from error

    async def generate_practice(
        self,
        *,
        learner_id: int,
        recommendation_id: int,
        expected_learning_update_id: int,
    ) -> AgentGenerationOutcome:
        return await self._generation_service().generate_or_resolve_current(
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            expected_learning_update_id=expected_learning_update_id,
        )

    async def submit_practice(self, *, learner_id: int, practice_id: int, essay: str):
        return await self._submission_service().submit(
            learner_id=learner_id,
            practice_id=practice_id,
            submission=PracticeSubmission(essay=essay),
        )

    def complete_practice(self, *, learner_id: int, practice_id: int):
        return self._completion_service().complete_with_outcome(
            learner_id=learner_id,
            practice_id=practice_id,
        )