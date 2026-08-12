"""Production provider composition for the writing API."""

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.llm import DeepSeekProvider, DeepSeekSettings, LLMProvider


def get_writing_provider() -> LLMProvider:
    """Build only the production DeepSeek provider from environment settings."""

    try:
        settings = DeepSeekSettings()
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Writing evaluation provider is unavailable.",
        ) from None
    return DeepSeekProvider(settings)
