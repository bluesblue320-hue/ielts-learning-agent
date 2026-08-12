"""Deterministic test-only implementation of the LLM provider contract."""

from collections import deque
from collections.abc import Iterable, Mapping
from typing import TypeAlias

from pydantic import ValidationError

from app.llm import (
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorContext,
    WritingProviderRequest,
)
from app.schemas.writing import StructuredProviderResult


FakeEffect: TypeAlias = (
    StructuredProviderResult | Mapping[str, object] | ProviderError
)


class FakeProvider:
    """Scripted provider used only through explicit test imports."""

    def __init__(
        self,
        effects: Iterable[FakeEffect],
        *,
        provider_name: str = "fake-provider",
        model_name: str = "fake-model",
    ) -> None:
        self._effects = deque(effects)
        self._provider_name = provider_name
        self._model_name = model_name
        self.requests: list[WritingProviderRequest] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def evaluate_writing(
        self,
        request: WritingProviderRequest,
    ) -> StructuredProviderResult:
        self.requests.append(request.model_copy(deep=True))
        if not self._effects:
            raise AssertionError("FakeProvider has no scripted effect remaining")

        effect = self._effects.popleft()
        if isinstance(effect, ProviderError):
            raise effect

        try:
            return StructuredProviderResult.model_validate(effect)
        except ValidationError as error:
            raise ProviderError(
                ProviderErrorCategory.INVALID_RESPONSE,
                "Provider returned invalid structured output.",
                context=ProviderErrorContext(provider=self.provider_name),
            ) from error
