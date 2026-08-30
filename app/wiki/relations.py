"""Canonical application-owned structural relation ledger."""

from __future__ import annotations

from typing import Final

from app.schemas.wiki import (
    WikiRelation,
    WikiRelationAuthority,
    WikiRelationType,
)
from app.wiki.registry import CRITERION_PAGE_SPECS, WIKI_PAGES


def _build_relations() -> tuple[WikiRelation, ...]:
    authority = WikiRelationAuthority.APPLICATION_STRUCTURAL
    relations = [
        WikiRelation(
            relation_type=WikiRelationType.CONTAINS,
            authority=authority,
            source_page_id=page.parent_page_id,
            target_page_id=page.page_id,
        )
        for page in WIKI_PAGES
        if page.parent_page_id is not None
    ]
    for spec in CRITERION_PAGE_SPECS:
        criterion_page_id = f"writing-task2-{spec.slug}"
        for lower_band in range(9):
            relations.append(
                WikiRelation(
                    relation_type=WikiRelationType.ADJACENT_BAND,
                    authority=authority,
                    source_page_id=f"{criterion_page_id}-band-{lower_band}",
                    target_page_id=f"{criterion_page_id}-band-{lower_band + 1}",
                )
            )

    page_order = {page.page_id: index for index, page in enumerate(WIKI_PAGES)}
    relation_order = {
        WikiRelationType.CONTAINS: 0,
        WikiRelationType.ADJACENT_BAND: 1,
    }
    return tuple(
        sorted(
            relations,
            key=lambda relation: (
                relation_order[relation.relation_type],
                page_order[relation.source_page_id],
                page_order[relation.target_page_id],
            ),
        )
    )


WIKI_RELATIONS: Final = _build_relations()
