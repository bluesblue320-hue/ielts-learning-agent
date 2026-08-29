from collections import Counter

from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.wiki import WikiPageType
from app.wiki.registry import CANONICAL_PAGE_IDS, WIKI_PAGES, WIKI_PAGES_BY_ID


def test_registry_has_exact_page_type_counts_and_one_root() -> None:
    counts = Counter(page.page_type for page in WIKI_PAGES)
    assert len(WIKI_PAGES) == 58
    assert counts == {
        WikiPageType.ROOT: 1,
        WikiPageType.SECTION: 3,
        WikiPageType.CRITERION: 4,
        WikiPageType.BAND_DESCRIPTOR: 40,
        WikiPageType.TASK_RULE: 3,
        WikiPageType.TASK_TYPE: 7,
    }
    assert WIKI_PAGES[0].page_id == "writing-task2"
    assert WIKI_PAGES[0].parent_page_id is None


def test_registry_has_exact_canonical_ids_and_preorder() -> None:
    assert len(CANONICAL_PAGE_IDS) == len(set(CANONICAL_PAGE_IDS)) == 58
    assert CANONICAL_PAGE_IDS[:4] == (
        "writing-task2",
        "writing-task2-assessment",
        "writing-task2-task-response",
        "writing-task2-task-response-band-0",
    )
    assert CANONICAL_PAGE_IDS[12] == "writing-task2-task-response-band-9"
    assert CANONICAL_PAGE_IDS[-7:] == (
        "writing-task2-type-opinion",
        "writing-task2-type-discussion",
        "writing-task2-type-multi-part",
        "writing-task2-type-multi-part-opinion",
        "writing-task2-type-advantage-disadvantage",
        "writing-task2-type-positive-negative",
        "writing-task2-type-cause-solution",
    )
    assert tuple(WIKI_PAGES_BY_ID) == CANONICAL_PAGE_IDS


def test_registry_owns_all_knowledge_exactly_once_without_secondary_references() -> None:
    owned_ids = [knowledge_id for page in WIKI_PAGES for knowledge_id in page.knowledge_ids]
    canonical_ids = [unit.knowledge_id for unit in WRITING_TASK2_KNOWLEDGE_UNITS]
    assert len(owned_ids) == len(set(owned_ids)) == 54
    assert set(owned_ids) == set(canonical_ids)
    assert all(
        not page.knowledge_ids
        for page in WIKI_PAGES
        if page.page_type in {WikiPageType.ROOT, WikiPageType.SECTION}
    )
    assert all(
        len(page.knowledge_ids) == 1
        for page in WIKI_PAGES
        if page.page_type not in {WikiPageType.ROOT, WikiPageType.SECTION}
    )
    assert all(page.aliases == () for page in WIKI_PAGES)


def test_registry_has_exact_section_and_criterion_order() -> None:
    children = [
        page.page_id for page in WIKI_PAGES if page.parent_page_id == "writing-task2"
    ]
    assert children == [
        "writing-task2-assessment",
        "writing-task2-task-rules",
        "writing-task2-task-types",
    ]
    criteria = [
        page.page_id
        for page in WIKI_PAGES
        if page.parent_page_id == "writing-task2-assessment"
    ]
    assert criteria == [
        "writing-task2-task-response",
        "writing-task2-coherence-and-cohesion",
        "writing-task2-lexical-resource",
        "writing-task2-grammatical-range-and-accuracy",
    ]
