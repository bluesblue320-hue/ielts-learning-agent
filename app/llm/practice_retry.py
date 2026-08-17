"""Bounded retries for the focused Phase 4 practice generator."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.llm.practice_generator import PracticeGenerationRequest, PracticeGenerator
from app.llm.provider import ProviderError, ThinkingMode
from app.llm.retry import ProviderRetryPolicy
from app.schemas.practice import GeneratedWritingPractice


class RetryingPracticeGenerator:
    """Apply the established provider retry policy to practice generation."""

    def __init__(
        self,
        generator: PracticeGenerator,
        policy: ProviderRetryPolicy | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._generator = generator
        self._policy = policy or ProviderRetryPolicy()
        self._sleeper = sleeper

    @property
    def provider_name(self) -> str:
        return self._generator.provider_name

    @property
    def model_name(self) -> str:
        return self._generator.model_name

    @property
    def thinking_mode(self) -> ThinkingMode:
        return self._generator.thinking_mode

    async def generate_practice(
        self,
        request: PracticeGenerationRequest,
    ) -> GeneratedWritingPractice:
        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                return await self._generator.generate_practice(request)
            except ProviderError as error:
                if not self._policy.should_retry(error, attempt):
                    raise
                await self._sleeper(self._policy.delay_after_attempt(attempt))
        raise AssertionError("bounded practice-generator retry loop exhausted unexpectedly")
