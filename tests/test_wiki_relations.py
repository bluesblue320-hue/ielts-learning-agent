from collections import Counter

from app.schemas.wiki import (
    WikiRelationAuthority,
    WikiRelationType,
)
from app.wiki.registry import WIKI_PAGES
from app.wiki.relations import WIKI_RELATIONS


def test_relation_ledger_has_exact_counts_and_authority() -> None:
    counts = Counter(relation.relation_type for relation in WIKI_RELATIONS)
    assert len(WIKI_RELATIONS) == 93
    assert counts == {
        WikiRelationType.CONTAINS: 57,
        WikiRelationType.ADJACENT_BAND: 36,
    }
    assert all(
        relation.authority is WikiRelationAuthority.APPLICATION_STRUCTURAL
        for relation in WIKI_RELATIONS
    )


def test_relation_ledger_has_no_self_or_duplicate_edges() -> None:
    keys = [
        (
            relation.relation_type,
            relation.source_page_id,
            relation.target_page_id,
        )
        for relation in WIKI_RELATIONS
    ]
    assert len(keys) == len(set(keys))
    assert all(source != target for _, source, target in keys)


def test_contains_relations_are_exact_direct_parent_edges() -> None:
    expected = {
        (page.parent_page_id, page.page_id)
        for page in WIKI_PAGES
        if page.parent_page_id is not None
    }
    actual = {
        (relation.source_page_id, relation.target_page_id)
        for relation in WIKI_RELATIONS
        if relation.relation_type is WikiRelationType.CONTAINS
    }
    assert actual == expected


def test_adjacent_band_relations_are_lower_to_higher_within_criterion() -> None:
    adjacent = [
        relation
        for relation in WIKI_RELATIONS
        if relation.relation_type is WikiRelationType.ADJACENT_BAND
    ]
    for relation in adjacent:
        source_prefix, source_band = relation.source_page_id.rsplit("-band-", 1)
        target_prefix, target_band = relation.target_page_id.rsplit("-band-", 1)
        assert source_prefix == target_prefix
        assert int(target_band) == int(source_band) + 1


def test_relation_ledger_uses_frozen_global_order() -> None:
    page_order = {page.page_id: index for index, page in enumerate(WIKI_PAGES)}
    type_order = {
        WikiRelationType.CONTAINS: 0,
        WikiRelationType.ADJACENT_BAND: 1,
    }
    assert list(WIKI_RELATIONS) == sorted(
        WIKI_RELATIONS,
        key=lambda relation: (
            type_order[relation.relation_type],
            page_order[relation.source_page_id],
            page_order[relation.target_page_id],
        ),
    )
