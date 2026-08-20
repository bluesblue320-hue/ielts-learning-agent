"""Direct existing-service adapters for one deterministic Agent turn."""

from __future__ import annotations

from collections.abc import Callable
from sqlalchemy.orm import Session

from app.schemas.practice import PracticeSubmission
from app.services.practice_completion import PracticeCompletionService
from app.services.practice_generation import AgentGenerationOutcome, PracticeGenerationService
from app.services.practice_submission import PracticeSubmissionService
from app.services.writing_evaluation import WritingEvaluationService


class AgentTools:
    """Thin direct adapters; provider-backed services are created on demand."""

    def __init__(self, *, generation: PracticeGenerationService | None = None, submission: PracticeSubmissionService | None = None, completion: PracticeCompletionService | None = None, session: Session | None = None, generator_factory: Callable[[], object] | None = None, provider_factory: Callable[[], object] | None = None) -> None:
        self._generation = generation
        self._submission = submission
        self._completion = completion
        self._session = session
        self._generator_factory = generator_factory
        self._provider_factory = provider_factory

    def _generation_service(self) -> PracticeGenerationService:
        if self._generation is None:
            assert self._session is not None and self._generator_factory is not None
            self._generation = PracticeGenerationService(self._session, self._generator_factory())
        return self._generation

    def _submission_service(self) -> PracticeSubmissionService:
        if self._submission is None:
            assert self._session is not None and self._provider_factory is not None
            self._submission = PracticeSubmissionService(self._session, WritingEvaluationService(self._provider_factory()))
        return self._submission

    def _completion_service(self) -> PracticeCompletionService:
        if self._completion is None:
            assert self._session is not None
            self._completion = PracticeCompletionService(self._session)
        return self._completion

    async def generate_practice(self, *, learner_id: int, recommendation_id: int, expected_learning_update_id: int) -> AgentGenerationOutcome:
        return await self._generation_service().generate_or_resolve_current(learner_id=learner_id, recommendation_id=recommendation_id, expected_learning_update_id=expected_learning_update_id)

    async def submit_practice(self, *, learner_id: int, practice_id: int, essay: str):
        return await self._submission_service().submit(learner_id=learner_id, practice_id=practice_id, submission=PracticeSubmission(essay=essay))

    def complete_practice(self, *, learner_id: int, practice_id: int):
        return self._completion_service().complete(learner_id=learner_id, practice_id=practice_id)