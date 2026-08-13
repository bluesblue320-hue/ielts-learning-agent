"""Typed vendor-independent boundaries for writing evaluation providers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.schemas.writing import (
    ProviderEvaluationPayload,
    WritingCriterion,
    WritingSubmission,
)


NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class ProviderBoundary(BaseModel):
    """Strict immutable base for provider request components."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TrustedEvaluationContext(ProviderBoundary):
    """Application-controlled instructions and contracts for evaluation."""

    evaluator_instructions: NonBlankText
    rubric_version: NonBlankText
    criterion_definitions: dict[WritingCriterion, NonBlankText]
    band_descriptors: dict[WritingCriterion, dict[str, NonBlankText]]
    half_band_guidance: NonBlankText
    task_length_guidance: NonBlankText
    submission_word_count: int = Field(gt=0)
    scoring_policy_version: NonBlankText
    scoring_policy: NonBlankText
    output_schema: dict[str, Any] = Field(min_length=1)
    prompt_version: NonBlankText
    safety_constraints: NonBlankText

    @model_validator(mode="after")
    def require_complete_rubric(self) -> TrustedEvaluationContext:
        """Require every criterion and every integer band anchor from 0 to 9."""

        expected = set(WritingCriterion)
        definition_criteria = set(self.criterion_definitions)
        descriptor_criteria = set(self.band_descriptors)
        if definition_criteria != expected or descriptor_criteria != expected:
            raise ValueError(
                "criterion_definitions and band_descriptors must contain "
                "exactly the four Writing Task 2 criteria"
            )
        expected_bands = {str(value) for value in range(10)}
        incomplete = [
            criterion.value
            for criterion, descriptors in self.band_descriptors.items()
            if set(descriptors) != expected_bands
        ]
        if incomplete:
            raise ValueError(
                "band_descriptors must contain integer anchors 0 through 9 "
                f"for every criterion; incomplete={sorted(incomplete)}"
            )
        return self


class WritingProviderRequest(ProviderBoundary):
    """One provider request with an explicit application trust boundary."""

    trusted_context: TrustedEvaluationContext
    untrusted_submission: WritingSubmission


class ThinkingMode(StrEnum):
    """Explicit application-owned provider reasoning mode."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class ProviderErrorCategory(StrEnum):
    """Stable provider failure distinctions required by downstream code."""

    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    BILLING = "billing"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    INVALID_RESPONSE = "invalid_response"
    REQUEST_REJECTED = "request_rejected"


@dataclass(frozen=True, slots=True)
class ProviderErrorContext:
    """Safe normalized context retained across provider implementations."""

    provider: str
    operation: str = "evaluate_writing"
    status_code: int | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must be non-blank")
        if not self.operation.strip():
            raise ValueError("operation must be non-blank")
        if self.status_code is not None and not 100 <= self.status_code <= 599:
            raise ValueError("status_code must be a valid HTTP status")
        if self.request_id is not None and not self.request_id.strip():
            raise ValueError("request_id must be non-blank when supplied")


class ProviderError(RuntimeError):
    """Normalized safe provider failure without retry or HTTP mapping policy."""

    def __init__(
        self,
        category: ProviderErrorCategory,
        safe_message: str,
        *,
        context: ProviderErrorContext,
    ) -> None:
        if not safe_message.strip():
            raise ValueError("safe_message must be non-blank")
        self.category = category
        self.safe_message = safe_message
        self.context = context
        super().__init__(safe_message)


@runtime_checkable
class LLMProvider(Protocol):
    """Asynchronous provider contract consumed by writing evaluation."""

    @property
    def provider_name(self) -> str:
        """Return the stable provider identifier."""

    @property
    def model_name(self) -> str:
        """Return the configured model identifier."""

    @property
    def thinking_mode(self) -> ThinkingMode:
        """Return the explicit application-configured reasoning mode."""

    async def evaluate_writing(
        self,
        request: WritingProviderRequest,
    ) -> ProviderEvaluationPayload:
        """Return a validated structured result or raise ProviderError."""

        ...
