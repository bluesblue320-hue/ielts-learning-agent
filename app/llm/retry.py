"""Bounded retry policy for normalized provider failures."""

from dataclasses import dataclass
from typing import Final

from app.llm.provider import (
    LLMProvider,
    ProviderError,
    ProviderErrorCategory,
    WritingProviderRequest,
)
from app.schemas.writing import StructuredProviderResult


RETRYABLE_PROVIDER_ERRORS: Final[frozenset[ProviderErrorCategory]] = frozenset(
    {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMIT,
        ProviderErrorCategory.TRANSIENT,
    }
)
MAX_PROVIDER_ATTEMPTS: Final[int] = 3


@dataclass(frozen=True, slots=True)
class ProviderRetryPolicy:
    """Permit at most three attempts for justified transient failures."""

    max_attempts: int = MAX_PROVIDER_ATTEMPTS

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= MAX_PROVIDER_ATTEMPTS:
            raise ValueError(
                f"max_attempts must be between 1 and {MAX_PROVIDER_ATTEMPTS}"
            )

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
    ) -> None:
        self._provider = provider
        self._policy = policy or ProviderRetryPolicy()

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    async def evaluate_writing(
        self,
        request: WritingProviderRequest,
    ) -> StructuredProviderResult:
        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                return await self._provider.evaluate_writing(request)
            except ProviderError as error:
                if not self._policy.should_retry(error, attempt):
                    raise
        raise AssertionError("bounded provider retry loop exhausted unexpectedly")
