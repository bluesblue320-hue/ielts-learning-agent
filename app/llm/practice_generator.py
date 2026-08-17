"""Focused PracticeGenerator contract (P4-07).

The smallest async generator abstraction for Phase 4 targeted Writing
practice. It is deliberately NOT a generic model gateway, tool framework,
agent runtime, or a second evaluator protocol: it carries application-owned
authority values only, and its structured output mirrors those authority
values for validation.

Authority rule: the persisted PracticeRecommendation controls WHAT
(target_skill, decision type, planner version); the generator controls HOW.
Any generated field that mirrors application-owned authority MUST equal the
application value; a mismatch is an invalid provider response (no practice
row, safe normalized failure).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.llm.provider import ProviderError
from app.schemas.learner import WritingSkillKey
from app.schemas.practice import GeneratedWritingPractice

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class GeneratorBoundary(BaseModel):
    """Strict immutable base for generator request/response boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PracticeGenerationRequest(GeneratorBoundary):
    """Application-owned authority values for one practice generation.

    Read-only values copied from the persisted recommendation. The model
    must never be allowed to override these fields.
    """

    recommendation_id: int = Field(gt=0)
    target_skill: WritingSkillKey
    learner_target_band: Decimal | None = None
    reason_codes: list[str] = Field(default_factory=list)
    planner_version: NonBlankText
    generator_policy_version: NonBlankText
    prompt_version: NonBlankText


@runtime_checkable
class PracticeGenerator(Protocol):
    """Asynchronous generator contract consumed by the generation service.

    Implementations MUST NOT mutate learner state, MUST NOT choose the target
    skill, and MUST raise ``ProviderError`` (normalized) on failure. The
    returned ``GeneratedWritingPractice.target_skill`` must equal the request
    authority value; the caller validates the mirror.
    """

    @property
    def provider_name(self) -> str:
        """Return the stable provider identifier."""

    @property
    def model_name(self) -> str:
        """Return the configured model identifier."""

    async def generate_practice(
        self,
        request: PracticeGenerationRequest,
    ) -> GeneratedWritingPractice:
        """Return validated structured practice content or raise
        ``ProviderError``."""
        ...
