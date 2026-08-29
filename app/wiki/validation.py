"""Full deterministic validation for the canonical Writing Wiki snapshot."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.knowledge import (
    KNOWLEDGE_VERSION,
    KnowledgeCategory,
    KnowledgeSource,
    KnowledgeUnit,
)
from app.schemas.wiki import (
    NAVIGATION_VERSION,
    WIKI_ROOT_PAGE_ID,
    WIKI_VERSION,
    WikiPage,
    WikiPageType,
    WikiRelation,
    WikiRelationAuthority,
    WikiRelationType,
)
from app.wiki.errors import WikiIntegrityError, WikiLookupInvalidError
from app.wiki.identity import normalize_wiki_identity
from app.wiki.registry import (
    CANONICAL_PAGE_IDS,
    CRITERION_PAGE_SPECS,
    WIKI_PAGES,
    WIKI_PAGES_BY_ID,
)
from app.wiki.relations import WIKI_RELATIONS


_PAGE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_RELATION_FIELDS = {
    "relation_type",
    "authority",
    "source_page_id",
    "target_page_id",
}


def _fail(message: str) -> None:
    raise WikiIntegrityError(message)


def _validate_pages(pages: Sequence[WikiPage]) -> dict[str, WikiPage]:
    if len(pages) != 58:
        _fail("wiki must contain exactly 58 pages")
    page_ids = [page.page_id for page in pages]
    if len(page_ids) != len(set(page_ids)):
        _fail("wiki page IDs must be unique")
    if set(page_ids) != set(CANONICAL_PAGE_IDS):
        _fail("wiki page set differs from the frozen registry")
    if tuple(page_ids) != CANONICAL_PAGE_IDS:
        _fail("wiki pages are not in canonical preorder")

    page_by_id = {page.page_id: page for page in pages}
    for page in pages:
        if not _PAGE_ID_PATTERN.fullmatch(page.page_id):
            _fail("wiki page ID is invalid")
        if page.wiki_version != WIKI_VERSION:
            _fail("wiki page version mismatch")
        if page.navigation_version != NAVIGATION_VERSION:
            _fail("wiki navigation version mismatch")
        if not isinstance(page.page_type, WikiPageType):
            _fail("wiki page type is invalid")
        if page.aliases:
            _fail("Wiki v1 aliases must be explicitly empty")
        if page != WIKI_PAGES_BY_ID[page.page_id]:
            _fail("wiki page metadata differs from the frozen contract")

    roots = [page for page in pages if page.page_type is WikiPageType.ROOT]
    if len(roots) != 1 or roots[0].page_id != WIKI_ROOT_PAGE_ID:
        _fail("wiki must have exactly the canonical root")
    if roots[0].parent_page_id is not None:
        _fail("wiki root cannot have a parent")
    for page in pages:
        if page.page_id == WIKI_ROOT_PAGE_ID:
            continue
        if page.parent_page_id is None or page.parent_page_id not in page_by_id:
            _fail("non-root Wiki page has an unknown parent")

    _validate_page_type_parent_compatibility(page_by_id)
    _validate_tree_and_order(pages, page_by_id)
    _validate_identity_space(pages)
    return page_by_id


def _validate_page_type_parent_compatibility(
    page_by_id: Mapping[str, WikiPage],
) -> None:
    for page in page_by_id.values():
        parent = (
            page_by_id.get(page.parent_page_id)
            if page.parent_page_id is not None
            else None
        )
        if page.page_type is WikiPageType.SECTION:
            if parent is None or parent.page_type is not WikiPageType.ROOT:
                _fail("section page must be a direct child of the root")
        elif page.page_type is WikiPageType.CRITERION:
            if page.parent_page_id != "writing-task2-assessment":
                _fail("criterion page has an invalid parent")
        elif page.page_type is WikiPageType.BAND_DESCRIPTOR:
            if parent is None or parent.page_type is not WikiPageType.CRITERION:
                _fail("band page must belong to a criterion")
        elif page.page_type is WikiPageType.TASK_RULE:
            if page.parent_page_id != "writing-task2-task-rules":
                _fail("task-rule page has an invalid parent")
        elif page.page_type is WikiPageType.TASK_TYPE:
            if page.parent_page_id != "writing-task2-task-types":
                _fail("task-type page has an invalid parent")


def _validate_tree_and_order(
    pages: Sequence[WikiPage], page_by_id: Mapping[str, WikiPage]
) -> None:
    children: dict[str, list[WikiPage]] = defaultdict(list)
    for page in pages:
        if page.parent_page_id is not None:
            children[page.parent_page_id].append(page)
    for siblings in children.values():
        siblings.sort(key=lambda page: page.order)
        if [page.order for page in siblings] != list(range(1, len(siblings) + 1)):
            _fail("sibling order must be contiguous and one-based")

    visiting: set[str] = set()
    visited: set[str] = set()
    preorder: list[str] = []

    def visit(page_id: str) -> None:
        if page_id in visiting:
            _fail("wiki contains hierarchy has a cycle")
        if page_id in visited:
            return
        visiting.add(page_id)
        preorder.append(page_id)
        for child in children.get(page_id, []):
            visit(child.page_id)
        visiting.remove(page_id)
        visited.add(page_id)

    visit(WIKI_ROOT_PAGE_ID)
    if visited != set(page_by_id):
        _fail("wiki contains an orphan or unreachable page")
    if tuple(preorder) != CANONICAL_PAGE_IDS:
        _fail("wiki tree traversal differs from canonical preorder")


def _validate_identity_space(pages: Sequence[WikiPage]) -> None:
    identities: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for page in pages:
        try:
            normalized_id = normalize_wiki_identity(page.page_id)
            normalized_title = normalize_wiki_identity(page.title)
        except WikiLookupInvalidError as error:
            raise WikiIntegrityError("wiki identity metadata is invalid") from error
        identities[normalized_id].append((page.page_id, "id"))
        identities[normalized_title].append((page.page_id, "title"))
        for alias in page.aliases:
            identities[normalize_wiki_identity(alias)].append((page.page_id, "alias"))
    if any(len(matches) != 1 for matches in identities.values()):
        _fail("wiki identity space is ambiguous")


def _validate_knowledge(
    pages: Sequence[WikiPage],
    knowledge_units: Sequence[KnowledgeUnit],
    sources: Mapping[str, KnowledgeSource],
) -> None:
    if len(knowledge_units) != 54:
        _fail("wiki requires the exact 54-unit Knowledge snapshot")
    unit_ids = [unit.knowledge_id for unit in knowledge_units]
    if len(unit_ids) != len(set(unit_ids)):
        _fail("Knowledge IDs must be unique")
    canonical_by_id = {
        unit.knowledge_id: unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS
    }
    if set(unit_ids) != set(canonical_by_id):
        _fail("wiki Knowledge snapshot differs from the canonical snapshot")
    unit_by_id = {unit.knowledge_id: unit for unit in knowledge_units}
    for unit in knowledge_units:
        if unit.knowledge_version != KNOWLEDGE_VERSION:
            _fail("Knowledge version mismatch")
        if unit != canonical_by_id[unit.knowledge_id]:
            _fail("canonical Knowledge identity or content was altered")
        for reference in unit.source_refs:
            source = sources.get(reference.source_id)
            if source is None or source.source_id != reference.source_id:
                _fail("Knowledge provenance does not resolve")
            canonical_source = KNOWLEDGE_SOURCES.get(reference.source_id)
            if canonical_source is None or source != canonical_source:
                _fail("Knowledge source identity was altered")

    owned_ids = [knowledge_id for page in pages for knowledge_id in page.knowledge_ids]
    if len(owned_ids) != 54 or len(set(owned_ids)) != 54:
        _fail("Wiki primary Knowledge ownership is missing or duplicated")
    if set(owned_ids) != set(unit_by_id):
        _fail("Wiki ownership does not cover the canonical Knowledge snapshot")

    criterion_by_page_id = {
        f"writing-task2-{spec.slug}": spec.key for spec in CRITERION_PAGE_SPECS
    }
    for page in pages:
        if page.page_type in {WikiPageType.ROOT, WikiPageType.SECTION}:
            if page.knowledge_ids:
                _fail("organization pages cannot own Knowledge")
            continue
        if len(page.knowledge_ids) != 1:
            _fail("factual Wiki page must own exactly one KnowledgeUnit")
        unit = unit_by_id.get(page.knowledge_ids[0])
        if unit is None:
            _fail("Wiki page owns unknown Knowledge")
        if page.page_type is WikiPageType.CRITERION:
            if unit.category is not KnowledgeCategory.ASSESSMENT:
                _fail("criterion page owns the wrong Knowledge category")
            if unit.criterion != criterion_by_page_id[page.page_id]:
                _fail("criterion page owns mismatched Knowledge")
        elif page.page_type is WikiPageType.BAND_DESCRIPTOR:
            assert page.parent_page_id is not None
            expected_criterion = criterion_by_page_id[page.parent_page_id]
            expected_band = int(page.page_id.rsplit("-", 1)[1])
            if (
                unit.category is not KnowledgeCategory.BAND_GUIDANCE
                or unit.criterion != expected_criterion
                or unit.descriptor_band != expected_band
            ):
                _fail("band page owns mismatched Knowledge")
        elif page.page_type is WikiPageType.TASK_RULE:
            if unit.category is not KnowledgeCategory.TASK_RULE:
                _fail("task-rule page owns the wrong Knowledge category")
        elif page.page_type is WikiPageType.TASK_TYPE:
            if unit.category is not KnowledgeCategory.TASK_UNDERSTANDING:
                _fail("task-type page owns the wrong Knowledge category")
            expected_type = page.page_id.removeprefix("writing-task2-type-").replace(
                "-", "_"
            )
            if unit.task_type != expected_type:
                _fail("task-type page owns mismatched Knowledge")


def _validate_relations(
    pages: Sequence[WikiPage], relations: Sequence[WikiRelation]
) -> None:
    if len(relations) != 93:
        _fail("wiki must contain exactly 93 canonical relations")
    page_ids = {page.page_id for page in pages}
    relation_keys: list[tuple[object, str, str]] = []
    counts: Counter[WikiRelationType] = Counter()
    for relation in relations:
        if set(relation.__dict__) != _RELATION_FIELDS:
            _fail("Wiki relation carries prohibited semantic fields")
        if not isinstance(relation.relation_type, WikiRelationType):
            _fail("Wiki relation type is invalid")
        if relation.authority is not WikiRelationAuthority.APPLICATION_STRUCTURAL:
            _fail("Wiki relation authority is invalid")
        if relation.source_page_id not in page_ids or relation.target_page_id not in page_ids:
            _fail("Wiki relation has an unknown endpoint")
        if relation.source_page_id == relation.target_page_id:
            _fail("Wiki relation cannot be a self-edge")
        relation_keys.append(
            (
                relation.relation_type,
                relation.source_page_id,
                relation.target_page_id,
            )
        )
        counts[relation.relation_type] += 1
    if len(relation_keys) != len(set(relation_keys)):
        _fail("Wiki relations must be unique")
    if counts != {
        WikiRelationType.CONTAINS: 57,
        WikiRelationType.ADJACENT_BAND: 36,
    }:
        _fail("Wiki relation counts differ from the frozen contract")

    expected_contains = {
        (page.parent_page_id, page.page_id)
        for page in pages
        if page.parent_page_id is not None
    }
    actual_contains = {
        (relation.source_page_id, relation.target_page_id)
        for relation in relations
        if relation.relation_type is WikiRelationType.CONTAINS
    }
    if actual_contains != expected_contains:
        _fail("contains relations differ from canonical parent assignments")

    expected_adjacent = {
        (
            f"writing-task2-{spec.slug}-band-{band}",
            f"writing-task2-{spec.slug}-band-{band + 1}",
        )
        for spec in CRITERION_PAGE_SPECS
        for band in range(9)
    }
    actual_adjacent = {
        (relation.source_page_id, relation.target_page_id)
        for relation in relations
        if relation.relation_type is WikiRelationType.ADJACENT_BAND
    }
    if actual_adjacent != expected_adjacent:
        _fail("adjacent-band relations differ from the frozen contract")

    page_order = {page.page_id: index for index, page in enumerate(pages)}
    type_order = {
        WikiRelationType.CONTAINS: 0,
        WikiRelationType.ADJACENT_BAND: 1,
    }
    ordered = sorted(
        relations,
        key=lambda relation: (
            type_order[relation.relation_type],
            page_order[relation.source_page_id],
            page_order[relation.target_page_id],
        ),
    )
    if list(relations) != ordered:
        _fail("Wiki relation ledger order is not canonical")


def validate_wiki_snapshot(
    *,
    pages: Sequence[WikiPage] = WIKI_PAGES,
    relations: Sequence[WikiRelation] = WIKI_RELATIONS,
    knowledge_units: Sequence[KnowledgeUnit] = WRITING_TASK2_KNOWLEDGE_UNITS,
    sources: Mapping[str, KnowledgeSource] = KNOWLEDGE_SOURCES,
) -> None:
    """Validate the complete static snapshot without repairing any input."""
    page_by_id = _validate_pages(pages)
    del page_by_id
    _validate_knowledge(pages, knowledge_units, sources)
    _validate_relations(pages, relations)
