"""Production composition for Phase 4 practice generation."""

from pydantic import ValidationError

from app.llm import (
    DeepSeekPracticeGenerator,
    DeepSeekSettings,
    PracticeGenerator,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorContext,
    RetryingPracticeGenerator,
)


def get_practice_generator() -> PracticeGenerator:
    """Build the production generator; tests override this dependency."""

    try:
        settings = DeepSeekSettings()
    except ValidationError:
        raise ProviderError(
            ProviderErrorCategory.CONFIGURATION,
            "Writing practice generator is not configured.",
            context=ProviderErrorContext(
                provider="deepseek",
                operation="generate_practice",
            ),
        ) from None
    return RetryingPracticeGenerator(DeepSeekPracticeGenerator(settings))
