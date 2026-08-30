import pytest

from app.schemas.wiki import WikiNeighborDirection, WikiRelationType
from app.wiki.errors import (
    WikiLookupAmbiguousError,
    WikiLookupInvalidError,
    WikiPageNotFoundError,
)
from app.wiki.identity import normalize_wiki_identity
from app.wiki.service import WikiService


def test_index_is_stable_complete_preorder() -> None:
    response = WikiService().index()
    assert len(response.pages) == 58
    assert len({page.page_id for page in response.pages}) == 58
    assert response.root_page_id == "writing-task2"
    assert response.pages[0].page_id == "writing-task2"
    assert response.pages[-1].page_id == "writing-task2-type-cause-solution"


def test_identity_resolution_is_exact_normalized_and_fail_closed() -> None:
    service = WikiService()
    assert service.resolve_identity("writing-task2").page_id == "writing-task2"
    assert (
        service.resolve_identity("  ＷＲＩＴＩＮＧ   ＴＡＳＫ ２  ").page_id
        == "writing-task2"
    )
    assert (
        service.resolve_identity("task response band 7").page_id
        == "writing-task2-task-response-band-7"
    )
    with pytest.raises(WikiPageNotFoundError):
        service.resolve_identity("Task Response Band")
    with pytest.raises(WikiPageNotFoundError):
        service.resolve_identity("Response Band 7")
    with pytest.raises(WikiLookupInvalidError):
        service.resolve_identity("   ")
    with pytest.raises(WikiLookupInvalidError):
        service.resolve_identity("x" * 121)


def test_ambiguous_normalized_identity_fails_closed() -> None:
    service = WikiService()
    identity = normalize_wiki_identity("Writing Task 2")
    service._title_index[identity] = (
        service.get_page("writing-task2"),
        service.get_page("writing-task2-assessment"),
    )
    with pytest.raises(WikiLookupAmbiguousError):
        service.resolve_identity("Writing Task 2")


def test_knowledge_id_resolves_to_exact_primary_page() -> None:
    service = WikiService()
    assert (
        service.page_for_knowledge_id("writing-task-response-band-7").page_id
        == "writing-task2-task-response-band-7"
    )
    with pytest.raises(WikiPageNotFoundError):
        service.page_for_knowledge_id("unknown-knowledge")


def test_breadcrumbs_are_root_first_and_include_current_page() -> None:
    service = WikiService()
    page = service.get_page("writing-task2-task-response-band-7")
    assert [item.page_id for item in service.breadcrumbs(page)] == [
        "writing-task2",
        "writing-task2-assessment",
        "writing-task2-task-response",
        "writing-task2-task-response-band-7",
    ]
    root = service.get_page("writing-task2")
    assert [item.page_id for item in service.breadcrumbs(root)] == ["writing-task2"]


def test_children_incident_relations_and_neighbor_projection_are_exact() -> None:
    service = WikiService()
    criterion = service.get_page("writing-task2-task-response")
    assert len(service.children(criterion)) == 10
    assert len(service.incident_relations(criterion)) == 11
    criterion_neighbors = service.neighbors(criterion)
    assert [neighbor.direction for neighbor in criterion_neighbors] == [
        WikiNeighborDirection.PARENT,
        *([WikiNeighborDirection.CHILD] * 10),
    ]

    band7 = service.get_page("writing-task2-task-response-band-7")
    incident = service.incident_relations(band7)
    assert len(incident) == 3
    assert [relation.relation_type for relation in incident] == [
        WikiRelationType.CONTAINS,
        WikiRelationType.ADJACENT_BAND,
        WikiRelationType.ADJACENT_BAND,
    ]
    assert [neighbor.direction for neighbor in service.neighbors(band7)] == [
        WikiNeighborDirection.PARENT,
        WikiNeighborDirection.PREVIOUS_BAND,
        WikiNeighborDirection.NEXT_BAND,
    ]


def test_band_boundary_neighbors_do_not_overflow() -> None:
    service = WikiService()
    band0 = service.get_page("writing-task2-task-response-band-0")
    band9 = service.get_page("writing-task2-task-response-band-9")
    assert WikiNeighborDirection.PREVIOUS_BAND not in {
        item.direction for item in service.neighbors(band0)
    }
    assert WikiNeighborDirection.NEXT_BAND not in {
        item.direction for item in service.neighbors(band9)
    }


def test_page_detail_projects_canonical_knowledge_and_provenance() -> None:
    service = WikiService()
    detail = service.detail("writing-task2-task-response-band-7")
    assert len(detail.knowledge) == 1
    assert detail.knowledge[0].knowledge_id == "writing-task-response-band-7"
    assert detail.knowledge[0].statement
    assert detail.knowledge[0].sources
    assert all(source.source_id for source in detail.knowledge[0].sources)
    assert all(
        relation.authority == "application_structural"
        for relation in detail.relations
    )
    assert WikiService().detail("writing-task2").knowledge == ()
