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
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.llm.provider import ThinkingMode
from app.schemas.learner import WritingSkillKey
from app.schemas.practice import GeneratedWritingPractice

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class GeneratorBoundary(BaseModel):
    """Strict immutable base for generator request/response boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PracticeKnowledgeItem(GeneratorBoundary):
    knowledge_id: NonBlankText
    statement: NonBlankText
    source_ids: tuple[NonBlankText, ...] = Field(min_length=1)


class PracticeKnowledgeContext(GeneratorBoundary):
    knowledge_context_version: Literal["writing-practice-knowledge-context-v1"] = (
        "writing-practice-knowledge-context-v1"
    )
    knowledge_version: Literal["ielts-writing-knowledge-v1"] = (
        "ielts-writing-knowledge-v1"
    )
    retrieval_version: Literal["writing-knowledge-structured-v1"] = (
        "writing-knowledge-structured-v1"
    )
    items: tuple[PracticeKnowledgeItem, ...] = Field(min_length=1, max_length=7)


class PracticeGenerationRequest(GeneratorBoundary):
    """Application-owned authority values for one practice generation.

    Read-only values copied from the persisted recommendation. The model
    must never be allowed to override these fields.
    """

    recommendation_id: int = Field(gt=0)
    decision_type: Literal["practice"] = "practice"
    target_skill: WritingSkillKey
    learner_target_band: Decimal | None = None
    reason_codes: list[str] = Field(default_factory=list)
    planner_version: NonBlankText
    generator_policy_version: Literal[
        "writing-practice-generation-v1", "writing-practice-generation-v2"
    ]
    prompt_version: Literal["practice-generation-v1", "practice-generation-v2"]

    knowledge_context: PracticeKnowledgeContext | None = None

    @model_validator(mode="after")
    def _validate_version_pair(self) -> "PracticeGenerationRequest":
        is_v2 = self.generator_policy_version == "writing-practice-generation-v2"
        if is_v2 and (
            self.prompt_version != "practice-generation-v2"
            or self.knowledge_context is None
        ):
            raise ValueError(
                "v2 generation requires the v2 prompt and knowledge context"
            )
        if not is_v2 and (
            self.prompt_version != "practice-generation-v1"
            or self.knowledge_context is not None
        ):
            raise ValueError(
                "historical v1 generation cannot carry Phase 9 knowledge context"
            )
        return self


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

    @property
    def thinking_mode(self) -> ThinkingMode:
        """Return the configured thinking-mode provenance value."""

    async def generate_practice(
        self,
        request: PracticeGenerationRequest,
    ) -> GeneratedWritingPractice:
        """Return validated structured practice content or raise
        ``ProviderError``."""
        ...
