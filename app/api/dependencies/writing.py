"""Production provider composition for the writing API."""

from pydantic import ValidationError

from app.llm import (
    DeepSeekProvider,
    DeepSeekSettings,
    LLMProvider,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorContext,
    RetryingProvider,
)


def get_writing_provider() -> LLMProvider:
    """Build only the production DeepSeek provider from environment settings."""

    try:
        settings = DeepSeekSettings()
    except ValidationError:
        raise ProviderError(
            ProviderErrorCategory.CONFIGURATION,
            "Writing evaluation provider is not configured.",
            context=ProviderErrorContext(provider="deepseek"),
        ) from None
    return RetryingProvider(DeepSeekProvider(settings))
