"""Strict immutable boundaries for the Phase 11 Writing Wiki."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.knowledge import (
    KNOWLEDGE_VERSION,
    KnowledgeAuthority,
    KnowledgeCategory,
    KnowledgeSourceType,
    StableId,
    WritingTask2TaskType,
)
from app.schemas.learner import WritingSkillKey


WIKI_VERSION = "ielts-writing-wiki-v1"
NAVIGATION_VERSION = "writing-wiki-navigation-v1"
WIKI_ROOT_PAGE_ID = "writing-task2"

WikiPageId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    ),
]
WikiTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
WikiAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class WikiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WikiPageType(StrEnum):
    ROOT = "root"
    SECTION = "section"
    CRITERION = "criterion"
    BAND_DESCRIPTOR = "band_descriptor"
    TASK_RULE = "task_rule"
    TASK_TYPE = "task_type"


class WikiRelationType(StrEnum):
    CONTAINS = "contains"
    ADJACENT_BAND = "adjacent_band"


class WikiRelationAuthority(StrEnum):
    APPLICATION_STRUCTURAL = "application_structural"


class WikiNeighborDirection(StrEnum):
    PARENT = "parent"
    CHILD = "child"
    PREVIOUS_BAND = "previous_band"
    NEXT_BAND = "next_band"


class WikiPage(WikiSchema):
    wiki_version: Literal["ielts-writing-wiki-v1"] = WIKI_VERSION
    navigation_version: Literal["writing-wiki-navigation-v1"] = (
        NAVIGATION_VERSION
    )
    page_id: WikiPageId
    page_type: WikiPageType
    title: WikiTitle
    aliases: tuple[WikiAlias, ...] = ()
    parent_page_id: WikiPageId | None
    order: int = Field(ge=1)
    knowledge_ids: tuple[StableId, ...] = Field(default=(), max_length=1)

    @model_validator(mode="after")
    def _validate_root_parent_shape(self) -> "WikiPage":
        if self.page_type is WikiPageType.ROOT and self.parent_page_id is not None:
            raise ValueError("root page cannot have a parent")
        if self.page_type is not WikiPageType.ROOT and self.parent_page_id is None:
            raise ValueError("non-root page requires a parent")
        return self


class WikiRelation(WikiSchema):
    relation_type: WikiRelationType
    authority: WikiRelationAuthority
    source_page_id: WikiPageId
    target_page_id: WikiPageId


class WikiPageSummary(WikiSchema):
    page_id: WikiPageId
    page_type: WikiPageType
    title: WikiTitle
    aliases: tuple[WikiAlias, ...] = ()
    parent_page_id: WikiPageId | None
    order: int = Field(ge=1)
    has_knowledge: bool


class WikiBreadcrumb(WikiSchema):
    page_id: WikiPageId
    title: WikiTitle


class WikiSourceProjection(WikiSchema):
    source_id: StableId
    authority: KnowledgeAuthority
    publisher: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=2_000)
    source_type: KnowledgeSourceType
    verified_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_revision: str | None = Field(default=None, min_length=1, max_length=64)
    locator: str = Field(min_length=1, max_length=500)
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1, max_length=200)


class WikiKnowledgeProjection(WikiSchema):
    knowledge_id: StableId
    knowledge_version: Literal["ielts-writing-knowledge-v1"] = KNOWLEDGE_VERSION
    task: Literal["writing_task2"] = "writing_task2"
    category: KnowledgeCategory
    statement: str = Field(min_length=1, max_length=500)
    criterion: WritingSkillKey | None = None
    descriptor_band: int | None = Field(default=None, ge=0, le=9)
    task_type: WritingTask2TaskType | None = None
    sources: tuple[WikiSourceProjection, ...] = Field(min_length=1)


class WikiRelationView(WikiRelation):
    pass


class WikiNeighborView(WikiSchema):
    page_id: WikiPageId
    page_type: WikiPageType
    title: WikiTitle
    relation_type: WikiRelationType
    direction: WikiNeighborDirection


class WikiPageDetail(WikiSchema):
    wiki_version: Literal["ielts-writing-wiki-v1"] = WIKI_VERSION
    navigation_version: Literal["writing-wiki-navigation-v1"] = (
        NAVIGATION_VERSION
    )
    page: WikiPageSummary
    breadcrumbs: tuple[WikiBreadcrumb, ...] = Field(min_length=1)
    knowledge: tuple[WikiKnowledgeProjection, ...] = Field(max_length=1)
    children: tuple[WikiPageSummary, ...] = ()
    relations: tuple[WikiRelationView, ...] = ()
    neighbors: tuple[WikiNeighborView, ...] = ()


class WikiIndexResponse(WikiSchema):
    wiki_version: Literal["ielts-writing-wiki-v1"] = WIKI_VERSION
    navigation_version: Literal["writing-wiki-navigation-v1"] = (
        NAVIGATION_VERSION
    )
    root_page_id: Literal["writing-task2"] = WIKI_ROOT_PAGE_ID
    pages: tuple[WikiPageSummary, ...] = Field(min_length=1)
