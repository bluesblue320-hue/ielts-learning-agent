"""Bounded retry policy for normalized provider failures."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from app.llm.provider import (
    LLMProvider,
    ProviderError,
    ProviderErrorCategory,
    ThinkingMode,
    WritingProviderRequest,
)
from app.schemas.writing import ProviderEvaluationPayload


RETRYABLE_PROVIDER_ERRORS: Final[frozenset[ProviderErrorCategory]] = frozenset(
    {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMIT,
        ProviderErrorCategory.TRANSIENT,
    }
)
MAX_PROVIDER_ATTEMPTS: Final[int] = 3
BASE_RETRY_DELAY_SECONDS: Final[float] = 0.25


@dataclass(frozen=True, slots=True)
class ProviderRetryPolicy:
    """Permit at most three attempts for justified transient failures."""

    max_attempts: int = MAX_PROVIDER_ATTEMPTS
    base_delay_seconds: float = BASE_RETRY_DELAY_SECONDS

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= MAX_PROVIDER_ATTEMPTS:
            raise ValueError(
                f"max_attempts must be between 1 and {MAX_PROVIDER_ATTEMPTS}"
            )
        if self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be positive")

    def delay_after_attempt(self, attempt: int) -> float:
        """Return deterministic exponential backoff after a failed attempt."""

        if attempt < 1:
            raise ValueError("attempt must be positive")
        return self.base_delay_seconds * (2 ** (attempt - 1))

    def should_retry(self, error: ProviderError, attempt: int) -> bool:
        """Return whether another attempt is permitted after this failure."""

        return (
            error.category in RETRYABLE_PROVIDER_ERRORS
            and attempt < self.max_attempts
        )


class RetryingProvider:
    """Apply deterministic bounded retries without changing provider errors."""

    def __init__(
        self,
        provider: LLMProvider,
        policy: ProviderRetryPolicy | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._provider = provider
        self._policy = policy or ProviderRetryPolicy()
        self._sleeper = sleeper

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    @property
    def thinking_mode(self) -> ThinkingMode:
        return self._provider.thinking_mode

    async def evaluate_writing(
        self,
        request: WritingProviderRequest,
    ) -> ProviderEvaluationPayload:
        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                return await self._provider.evaluate_writing(request)
            except ProviderError as error:
                if not self._policy.should_retry(error, attempt):
                    raise
                await self._sleeper(
                    self._policy.delay_after_attempt(attempt)
                )
        raise AssertionError("bounded provider retry loop exhausted unexpectedly")
