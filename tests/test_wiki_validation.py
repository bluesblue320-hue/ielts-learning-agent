from types import MappingProxyType

import pytest

from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.schemas.wiki import WikiPage, WikiPageType, WikiRelation, WikiRelationType
from app.wiki.errors import WikiIntegrityError
from app.wiki.registry import WIKI_PAGES
from app.wiki.relations import WIKI_RELATIONS
from app.wiki.snapshot import VALIDATED_WIKI_SNAPSHOT
from app.wiki.validation import validate_wiki_snapshot


def _replace_page(
    canonical_page_id: str, **updates: object
) -> tuple[WikiPage, ...]:
    return tuple(
        page.model_copy(update=updates)
        if page.page_id == canonical_page_id
        else page
        for page in WIKI_PAGES
    )


def _replace_relation(index: int, **updates: object) -> tuple[WikiRelation, ...]:
    return tuple(
        relation.model_copy(update=updates) if offset == index else relation
        for offset, relation in enumerate(WIKI_RELATIONS)
    )


def _assert_invalid(**overrides: object) -> None:
    values = {
        "pages": WIKI_PAGES,
        "relations": WIKI_RELATIONS,
        "knowledge_units": VALIDATED_WIKI_SNAPSHOT.knowledge_units,
        "sources": KNOWLEDGE_SOURCES,
    }
    values.update(overrides)
    with pytest.raises(WikiIntegrityError):
        validate_wiki_snapshot(**values)


def test_canonical_snapshot_is_validated_once_for_application_use() -> None:
    validate_wiki_snapshot()
    assert len(VALIDATED_WIKI_SNAPSHOT.pages) == 58
    assert len(VALIDATED_WIKI_SNAPSHOT.relations) == 93


@pytest.mark.parametrize(
    "pages",
    [
        WIKI_PAGES + (WIKI_PAGES[0],),
        WIKI_PAGES[1:],
        WIKI_PAGES
        + (
            WikiPage(
                page_id="writing-task2-extra",
                page_type="section",
                title="Extra",
                parent_page_id="writing-task2",
                order=4,
            ),
        ),
        _replace_page("writing-task2-task-response", parent_page_id="writing-task2"),
        _replace_page(
            "writing-task2-task-response",
            page_type=WikiPageType.ROOT,
            parent_page_id=None,
        ),
        _replace_page(
            "writing-task2-task-response-band-7",
            parent_page_id="writing-task2-task-response-band-8",
        ),
        _replace_page(
            "writing-task2-task-response-band-7",
            title="Task Response Band 6",
        ),
        _replace_page(
            "writing-task2-task-response-band-7",
            knowledge_ids=("unknown-knowledge",),
        ),
        _replace_page(
            "writing-task2-task-response-band-7",
            knowledge_ids=("writing-task-response-band-6",),
        ),
        _replace_page(
            "writing-task2-task-response-band-7",
            knowledge_ids=("writing-task-response-criterion",),
        ),
        _replace_page(
            "writing-task2-task-response-band-7",
            knowledge_ids=(),
        ),
        _replace_page(
            "writing-task2-task-response-band-7",
            parent_page_id="writing-task2-missing-parent",
        ),
    ],
)
def test_validator_rejects_corrupted_page_and_ownership_snapshots(
    pages: tuple[WikiPage, ...]
) -> None:
    _assert_invalid(pages=pages)


def test_validator_rejects_malformed_page_id_bypassing_schema_validation() -> None:
    pages = _replace_page(
        "writing-task2-task-response-band-7",
        page_id="writing--task2-extra",
    )
    with pytest.raises(WikiIntegrityError, match="wiki page ID is invalid"):
        validate_wiki_snapshot(pages=pages)


def test_validator_rejects_missing_and_extra_contains_relations() -> None:
    contains_index = next(
        index
        for index, relation in enumerate(WIKI_RELATIONS)
        if relation.relation_type is WikiRelationType.CONTAINS
    )
    _assert_invalid(relations=WIKI_RELATIONS[:contains_index] + WIKI_RELATIONS[contains_index + 1 :])
    replacement = WIKI_RELATIONS[contains_index].model_copy(
        update={"target_page_id": "writing-task2-task-response-band-1"}
    )
    relations = list(WIKI_RELATIONS)
    relations[contains_index] = replacement
    _assert_invalid(relations=tuple(relations))


def test_validator_rejects_multiple_parent_cycle_and_unreachable_shapes() -> None:
    extra_parent = _replace_relation(
        57,
        relation_type=WikiRelationType.CONTAINS,
        source_page_id="writing-task2-assessment",
        target_page_id="writing-task2-task-response-band-7",
    )
    _assert_invalid(relations=extra_parent)

    pages = _replace_page(
        "writing-task2-task-response-band-7",
        parent_page_id="writing-task2-task-response-band-8",
    )
    pages = tuple(
        page.model_copy(
            update={"parent_page_id": "writing-task2-task-response-band-7"}
        )
        if page.page_id == "writing-task2-task-response-band-8"
        else page
        for page in pages
    )
    _assert_invalid(pages=pages)


def test_validator_rejects_missing_adjacent_relation() -> None:
    first_adjacent = next(
        index
        for index, relation in enumerate(WIKI_RELATIONS)
        if relation.relation_type is WikiRelationType.ADJACENT_BAND
    )
    _assert_invalid(
        relations=WIKI_RELATIONS[:first_adjacent]
        + WIKI_RELATIONS[first_adjacent + 1 :]
    )


@pytest.mark.parametrize(
    "relations",
    [
        _replace_relation(57, source_page_id="writing-task2-task-response-band-1", target_page_id="writing-task2-task-response-band-0"),
        _replace_relation(57, target_page_id="writing-task2-coherence-and-cohesion-band-1"),
        _replace_relation(57, target_page_id="writing-task2-task-response-band-2"),
        _replace_relation(57, source_page_id="writing-task2-task-response-band-0", target_page_id="writing-task2-task-response-band-0"),
        _replace_relation(57, authority="official_ielts"),
        _replace_relation(57, relation_type="related_to"),
    ],
)
def test_validator_rejects_corrupted_adjacent_relation_snapshots(
    relations: tuple[WikiRelation, ...]
) -> None:
    _assert_invalid(relations=relations)


def test_validator_rejects_relation_with_persisted_rationale() -> None:
    relation = WIKI_RELATIONS[0].model_copy()
    object.__setattr__(relation, "rationale", "prohibited")
    _assert_invalid(relations=(relation,) + WIKI_RELATIONS[1:])


def test_validator_rejects_unresolved_or_altered_provenance() -> None:
    missing_sources = dict(KNOWLEDGE_SOURCES)
    missing_sources.pop("ielts-writing-band-descriptors-2023")
    _assert_invalid(sources=MappingProxyType(missing_sources))

    altered_sources = dict(KNOWLEDGE_SOURCES)
    source = altered_sources["ielts-writing-band-descriptors-2023"]
    altered_sources[source.source_id] = source.model_copy(update={"title": "Altered"})
    _assert_invalid(sources=MappingProxyType(altered_sources))
