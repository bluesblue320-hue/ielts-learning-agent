"""Deterministic test-only Phase 4 practice generator."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from app.llm.practice_generator import PracticeGenerationRequest
from app.llm.provider import ProviderError, ThinkingMode
from app.schemas.practice import GeneratedWritingPractice


FakePracticeEffect = GeneratedWritingPractice | ProviderError


class FakePracticeGenerator:
    """Return policy-valid deterministic practice content for isolated tests."""

    def __init__(
        self,
        effects: Iterable[FakePracticeEffect] = (),
        *,
        provider_name: str = "fake-practice-provider",
        model_name: str = "fake-practice-model",
        thinking_mode: ThinkingMode = ThinkingMode.DISABLED,
    ) -> None:
        self._effects = deque(effects)
        self._provider_name = provider_name
        self._model_name = model_name
        self._thinking_mode = thinking_mode
        self.requests: list[PracticeGenerationRequest] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def thinking_mode(self) -> ThinkingMode:
        return self._thinking_mode

    async def generate_practice(
        self,
        request: PracticeGenerationRequest,
    ) -> GeneratedWritingPractice:
        self.requests.append(request.model_copy(deep=True))
        if self._effects:
            effect = self._effects.popleft()
            if isinstance(effect, ProviderError):
                raise effect
            return effect
        return GeneratedWritingPractice(
            practice_type="task2_targeted_focus",
            target_skill=request.target_skill,
            question=(
                "Some people believe governments should spend more on public "
                "transport than on building new roads. To what extent do you agree?"
            ),
            focus_objective=f"Develop a clear response focused on {request.target_skill}.",
            instructions=[
                "Write an original IELTS Academic Writing Task 2 response.",
                f"Prioritize {request.target_skill.replace('_', ' ')} throughout.",
            ],
            checkpoints=[
                "Address every part of the question.",
                "Check that your supporting ideas are specific and relevant.",
            ],
            generator_policy_version=request.generator_policy_version,
            provider=self.provider_name,
            model=self.model_name,
            prompt_version=request.prompt_version,
            thinking_mode=self.thinking_mode.value,
        )
