"""Strict, immutable Phase 9 IELTS Knowledge boundaries.

These schemas deliberately contain only learner-independent reference knowledge
and safe derived response projections.  They do not perform retrieval, access
the database, or call a provider.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.common import BandScore
from app.schemas.learner import DerivedStateBand, WritingSkillKey


KNOWLEDGE_VERSION = "ielts-writing-knowledge-v1"
RETRIEVAL_VERSION = "writing-knowledge-structured-v1"
GROUNDED_GUIDANCE_VERSION = "writing-grounded-guidance-v1"
WRITING_TASK = "writing_task2"

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
StableId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9-]*$")]


class KnowledgeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KnowledgeAuthority(StrEnum):
    OFFICIAL_IELTS = "official_ielts"
    OFFICIAL_BRITISH_COUNCIL = "official_british_council"
    OFFICIAL_IDP = "official_idp"


class KnowledgeSourceType(StrEnum):
    OFFICIAL_WEB_OR_PDF = "official_web_or_pdf"


class KnowledgeCategory(StrEnum):
    ASSESSMENT = "assessment"
    BAND_GUIDANCE = "band_guidance"
    TASK_RULE = "task_rule"
    TASK_UNDERSTANDING = "task_understanding"


class WritingTask2TaskType(StrEnum):
    OPINION = "opinion"
    DISCUSSION = "discussion"
    MULTI_PART = "multi_part"
    MULTI_PART_OPINION = "multi_part_opinion"
    ADVANTAGE_DISADVANTAGE = "advantage_disadvantage"
    POSITIVE_NEGATIVE = "positive_negative"
    CAUSE_SOLUTION = "cause_solution"


class KnowledgeRetrievalPurpose(StrEnum):
    PRACTICE_GENERATION = "practice_generation"
    LEARNER_GUIDANCE = "learner_guidance"
    RUBRIC_COMPATIBILITY = "rubric_compatibility"


class KnowledgeSource(KnowledgeSchema):
    source_id: StableId
    authority: KnowledgeAuthority
    publisher: NonBlankText
    title: NonBlankText
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]
    source_type: KnowledgeSourceType
    verified_at: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    content_scope: tuple[Literal["writing_task2"], ...] = (WRITING_TASK,)
    source_revision: str | None = Field(default=None, min_length=1, max_length=64)


class KnowledgeSourceRef(KnowledgeSchema):
    source_id: StableId
    locator: NonBlankText
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1, max_length=200)


class KnowledgeUnit(KnowledgeSchema):
    knowledge_id: StableId
    knowledge_version: Literal["ielts-writing-knowledge-v1"] = KNOWLEDGE_VERSION
    task: Literal["writing_task2"] = WRITING_TASK
    category: KnowledgeCategory
    criterion: WritingSkillKey | None = None
    descriptor_band: int | None = Field(default=None, ge=0, le=9)
    task_type: WritingTask2TaskType | None = None
    statement: NonBlankText
    source_refs: tuple[KnowledgeSourceRef, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def _validate_dimensions(self) -> "KnowledgeUnit":
        if self.category in {KnowledgeCategory.ASSESSMENT, KnowledgeCategory.BAND_GUIDANCE} and self.criterion is None:
            raise ValueError("criterion knowledge requires criterion")
        if self.descriptor_band is not None and self.criterion is None:
            raise ValueError("descriptor knowledge requires criterion")
        if self.category is KnowledgeCategory.TASK_UNDERSTANDING and self.task_type is None:
            raise ValueError("task understanding requires task_type")
        return self


class KnowledgeRetrievalQuery(KnowledgeSchema):
    task: Literal["writing_task2"] = WRITING_TASK
    purpose: KnowledgeRetrievalPurpose
    criterion: WritingSkillKey | None = None
    current_band: BandScore | None = None
    target_band: BandScore | None = None
    task_type: WritingTask2TaskType | None = None

    @model_validator(mode="after")
    def _validate_strategy_inputs(self) -> "KnowledgeRetrievalQuery":
        if self.criterion is None:
            raise ValueError("criterion is required for Phase 9 retrieval")
        if self.purpose is KnowledgeRetrievalPurpose.RUBRIC_COMPATIBILITY:
            if self.current_band is None:
                raise ValueError("rubric compatibility requires current_band")
        elif self.target_band is None or (self.purpose is KnowledgeRetrievalPurpose.LEARNER_GUIDANCE and self.current_band is None):
            raise ValueError("guidance requires current_band and target_band; generation requires target_band")
        return self


class KnowledgeRetrievalResult(KnowledgeSchema):
    knowledge_version: Literal["ielts-writing-knowledge-v1"] = KNOWLEDGE_VERSION
    retrieval_version: Literal["writing-knowledge-structured-v1"] = RETRIEVAL_VERSION
    query: KnowledgeRetrievalQuery
    units: tuple[KnowledgeUnit, ...]


class GroundedCitation(KnowledgeSchema):
    source_id: StableId
    publisher: NonBlankText
    title: NonBlankText
    url: str
    locator: NonBlankText
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1, max_length=200)


class GroundedGuidanceItem(KnowledgeSchema):
    criterion: WritingSkillKey
    title: NonBlankText
    explanation: NonBlankText
    knowledge_ids: tuple[StableId, ...] = Field(min_length=1)
    citations: tuple[GroundedCitation, ...] = Field(min_length=1)


class GroundedRecommendationSummary(KnowledgeSchema):
    id: int = Field(gt=0)
    decision_type: Literal["practice", "no_practice"]
    target_skill: WritingSkillKey | None = None
    learner_target_band: BandScore | None = None
    current_estimate: DerivedStateBand | None = None
    reason_codes: tuple[str, ...]


class GroundedLearnerStateSummary(KnowledgeSchema):
    learner_id: int = Field(gt=0)
    writing_target_band: BandScore
    current_estimates: dict[WritingSkillKey, DerivedStateBand | None]


class WritingGroundedGuidanceResponse(KnowledgeSchema):
    learner_state: GroundedLearnerStateSummary
    current_recommendation: GroundedRecommendationSummary | None = None
    guidance_items: tuple[GroundedGuidanceItem, ...] = ()
    source_citations: tuple[GroundedCitation, ...] = ()
    guidance_version: Literal["writing-grounded-guidance-v1"] = GROUNDED_GUIDANCE_VERSION
    knowledge_version: Literal["ielts-writing-knowledge-v1"] = KNOWLEDGE_VERSION
    retrieval_version: Literal["writing-knowledge-structured-v1"] = RETRIEVAL_VERSION
