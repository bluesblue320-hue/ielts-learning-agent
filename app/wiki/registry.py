"""Canonical Git-controlled registry for the Writing Task 2 Wiki."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from app.schemas.wiki import WikiPage, WikiPageType


@dataclass(frozen=True, slots=True)
class CriterionPageSpec:
    key: str
    slug: str
    title: str
    criterion_knowledge_id: str


CRITERION_PAGE_SPECS: Final = (
    CriterionPageSpec(
        key="task_response",
        slug="task-response",
        title="Task Response",
        criterion_knowledge_id="writing-task-response-criterion",
    ),
    CriterionPageSpec(
        key="coherence_and_cohesion",
        slug="coherence-and-cohesion",
        title="Coherence and Cohesion",
        criterion_knowledge_id="writing-coherence-and-cohesion-criterion",
    ),
    CriterionPageSpec(
        key="lexical_resource",
        slug="lexical-resource",
        title="Lexical Resource",
        criterion_knowledge_id="writing-lexical-resource-criterion",
    ),
    CriterionPageSpec(
        key="grammatical_range_and_accuracy",
        slug="grammatical-range-and-accuracy",
        title="Grammatical Range and Accuracy",
        criterion_knowledge_id="writing-grammatical-range-and-accuracy-criterion",
    ),
)

TASK_RULE_PAGE_SPECS: Final = (
    (
        "writing-task2-rule-minimum-250-words",
        "Minimum 250 Words",
        "writing-task2-minimum-250-words",
    ),
    (
        "writing-task2-rule-connected-text",
        "Connected Text",
        "writing-task2-connected-text",
    ),
    (
        "writing-task2-rule-answer-prompt-directly",
        "Answer the Prompt Directly",
        "writing-task2-answer-prompt-directly",
    ),
)

TASK_TYPE_PAGE_SPECS: Final = (
    ("writing-task2-type-opinion", "Opinion", "writing-task2-type-opinion"),
    (
        "writing-task2-type-discussion",
        "Discussion",
        "writing-task2-type-discussion",
    ),
    (
        "writing-task2-type-multi-part",
        "Multi-part",
        "writing-task2-type-multi-part",
    ),
    (
        "writing-task2-type-multi-part-opinion",
        "Multi-part Opinion",
        "writing-task2-type-multi-part-opinion",
    ),
    (
        "writing-task2-type-advantage-disadvantage",
        "Advantage / Disadvantage",
        "writing-task2-type-advantage-disadvantage",
    ),
    (
        "writing-task2-type-positive-negative",
        "Positive / Negative",
        "writing-task2-type-positive-negative",
    ),
    (
        "writing-task2-type-cause-solution",
        "Cause / Solution",
        "writing-task2-type-cause-solution",
    ),
)


def _page(
    *,
    page_id: str,
    page_type: WikiPageType,
    title: str,
    parent_page_id: str | None,
    order: int,
    knowledge_id: str | None = None,
) -> WikiPage:
    return WikiPage(
        page_id=page_id,
        page_type=page_type,
        title=title,
        aliases=(),
        parent_page_id=parent_page_id,
        order=order,
        knowledge_ids=() if knowledge_id is None else (knowledge_id,),
    )


def _build_pages() -> tuple[WikiPage, ...]:
    pages: list[WikiPage] = [
        _page(
            page_id="writing-task2",
            page_type=WikiPageType.ROOT,
            title="Writing Task 2",
            parent_page_id=None,
            order=1,
        ),
        _page(
            page_id="writing-task2-assessment",
            page_type=WikiPageType.SECTION,
            title="Assessment Criteria",
            parent_page_id="writing-task2",
            order=1,
        ),
    ]
    for criterion_order, spec in enumerate(CRITERION_PAGE_SPECS, start=1):
        criterion_page_id = f"writing-task2-{spec.slug}"
        pages.append(
            _page(
                page_id=criterion_page_id,
                page_type=WikiPageType.CRITERION,
                title=spec.title,
                parent_page_id="writing-task2-assessment",
                order=criterion_order,
                knowledge_id=spec.criterion_knowledge_id,
            )
        )
        for band in range(10):
            pages.append(
                _page(
                    page_id=f"{criterion_page_id}-band-{band}",
                    page_type=WikiPageType.BAND_DESCRIPTOR,
                    title=f"{spec.title} Band {band}",
                    parent_page_id=criterion_page_id,
                    order=band + 1,
                    knowledge_id=f"writing-{spec.slug}-band-{band}",
                )
            )
    pages.append(
        _page(
            page_id="writing-task2-task-rules",
            page_type=WikiPageType.SECTION,
            title="Task Rules",
            parent_page_id="writing-task2",
            order=2,
        )
    )
    for order, (page_id, title, knowledge_id) in enumerate(
        TASK_RULE_PAGE_SPECS, start=1
    ):
        pages.append(
            _page(
                page_id=page_id,
                page_type=WikiPageType.TASK_RULE,
                title=title,
                parent_page_id="writing-task2-task-rules",
                order=order,
                knowledge_id=knowledge_id,
            )
        )
    pages.append(
        _page(
            page_id="writing-task2-task-types",
            page_type=WikiPageType.SECTION,
            title="Task Types",
            parent_page_id="writing-task2",
            order=3,
        )
    )
    for order, (page_id, title, knowledge_id) in enumerate(
        TASK_TYPE_PAGE_SPECS, start=1
    ):
        pages.append(
            _page(
                page_id=page_id,
                page_type=WikiPageType.TASK_TYPE,
                title=title,
                parent_page_id="writing-task2-task-types",
                order=order,
                knowledge_id=knowledge_id,
            )
        )
    return tuple(pages)


WIKI_PAGES: Final = _build_pages()
WIKI_PAGES_BY_ID: Final[Mapping[str, WikiPage]] = MappingProxyType(
    {page.page_id: page for page in WIKI_PAGES}
)
CANONICAL_PAGE_IDS: Final = tuple(page.page_id for page in WIKI_PAGES)
