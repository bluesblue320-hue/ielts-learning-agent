from enum import StrEnum

import pytest
from pydantic import ValidationError

from app.schemas.wiki import (
    NAVIGATION_VERSION,
    WIKI_VERSION,
    WikiNeighborDirection,
    WikiPage,
    WikiPageType,
    WikiRelation,
    WikiRelationAuthority,
    WikiRelationType,
)


def test_wiki_enums_are_exact_closed_contracts() -> None:
    assert set(WikiPageType) == {
        WikiPageType.ROOT,
        WikiPageType.SECTION,
        WikiPageType.CRITERION,
        WikiPageType.BAND_DESCRIPTOR,
        WikiPageType.TASK_RULE,
        WikiPageType.TASK_TYPE,
    }
    assert set(WikiRelationType) == {
        WikiRelationType.CONTAINS,
        WikiRelationType.ADJACENT_BAND,
    }
    assert set(WikiRelationAuthority) == {
        WikiRelationAuthority.APPLICATION_STRUCTURAL
    }
    assert set(WikiNeighborDirection) == {
        WikiNeighborDirection.PARENT,
        WikiNeighborDirection.CHILD,
        WikiNeighborDirection.PREVIOUS_BAND,
        WikiNeighborDirection.NEXT_BAND,
    }
    assert all(issubclass(enum_type, StrEnum) for enum_type in (WikiPageType, WikiRelationType))


def test_wiki_page_is_strict_frozen_and_versioned() -> None:
    page = WikiPage(
        page_id="writing-task2",
        page_type="root",
        title="Writing Task 2",
        parent_page_id=None,
        order=1,
    )
    assert page.wiki_version == WIKI_VERSION
    assert page.navigation_version == NAVIGATION_VERSION
    with pytest.raises(ValidationError):
        WikiPage.model_validate({**page.model_dump(), "unexpected": True})
    with pytest.raises(ValidationError):
        page.title = "Changed"
    with pytest.raises(ValidationError):
        WikiPage.model_validate({**page.model_dump(), "wiki_version": "wiki-v2"})
    with pytest.raises(ValidationError):
        WikiPage.model_validate(
            {**page.model_dump(), "navigation_version": "navigation-v2"}
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"page_id": "Invalid ID"},
        {"title": " "},
        {"order": 0},
        {"page_type": "article"},
        {"parent_page_id": "writing-task2"},
    ],
)
def test_wiki_page_rejects_invalid_boundary_values(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "page_id": "writing-task2",
        "page_type": "root",
        "title": "Writing Task 2",
        "parent_page_id": None,
        "order": 1,
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        WikiPage.model_validate(values)


def test_wiki_relation_has_only_frozen_structural_fields() -> None:
    relation = WikiRelation(
        relation_type="contains",
        authority="application_structural",
        source_page_id="writing-task2",
        target_page_id="writing-task2-assessment",
    )
    assert set(relation.model_dump()) == {
        "relation_type",
        "authority",
        "source_page_id",
        "target_page_id",
    }
    with pytest.raises(ValidationError):
        WikiRelation.model_validate({**relation.model_dump(), "rationale": "No"})
    with pytest.raises(ValidationError):
        WikiRelation.model_validate(
            {**relation.model_dump(), "relation_type": "related_to"}
        )
    with pytest.raises(ValidationError):
        WikiRelation.model_validate(
            {**relation.model_dump(), "authority": "official_ielts"}
        )
