"""Direct existing-service adapters for one deterministic Agent turn."""

from __future__ import annotations

from app.schemas.practice import PracticeSubmission
from app.services.practice_completion import PracticeCompletionService
from app.services.practice_generation import AgentGenerationOutcome, PracticeGenerationService
from app.services.practice_submission import PracticeSubmissionService


class AgentTools:
    """Thin direct adapters; this is not an HTTP client or tool registry."""

    def __init__(
        self,
        *,
        generation: PracticeGenerationService,
        submission: PracticeSubmissionService,
        completion: PracticeCompletionService,
    ) -> None:
        self._generation = generation
        self._submission = submission
        self._completion = completion

    async def generate_practice(
        self,
        *,
        learner_id: int,
        recommendation_id: int,
        expected_learning_update_id: int,
    ) -> AgentGenerationOutcome:
        return await self._generation.generate_or_resolve_current(
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            expected_learning_update_id=expected_learning_update_id,
        )

    async def submit_practice(self, *, learner_id: int, practice_id: int, essay: str):
        return await self._submission.submit(
            learner_id=learner_id,
            practice_id=practice_id,
            submission=PracticeSubmission(essay=essay),
        )

    def complete_practice(self, *, learner_id: int, practice_id: int):
        return self._completion.complete(learner_id=learner_id, practice_id=practice_id)
