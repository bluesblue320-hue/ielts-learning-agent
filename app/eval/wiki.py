"""Provider-free Phase 11 Wiki evidence built on the Phase 10 Eval contracts."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence

from pydantic import Field

from app.eval.schemas import (
    EvalFinding,
    EvalSchema,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)
from app.knowledge.retriever import retrieve_knowledge
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.knowledge import KnowledgeRetrievalQuery, KnowledgeSource, KnowledgeUnit
from app.schemas.wiki import (
    WIKI_PAGE_ID_PATTERN,
    WikiNeighborDirection,
    WikiNeighborView,
    WikiPage,
    WikiPageType,
    WikiRelation,
    WikiRelationAuthority,
    WikiRelationType,
)
from app.wiki.errors import WikiIntegrityError, WikiPageNotFoundError
from app.wiki.registry import WIKI_PAGES
from app.wiki.relations import WIKI_RELATIONS
from app.wiki.service import WIKI_SERVICE
from app.wiki.validation import validate_wiki_snapshot


NeighborSemantic = tuple[
    str,
    WikiPageType,
    str,
    WikiRelationType,
    WikiNeighborDirection,
]


class WikiEvalEvidence(EvalSchema):
    """Application-shaped evidence for Wiki navigation and authority checks."""

    guidance_knowledge_ids: tuple[str, ...] = Field(min_length=1)
    guidance_page_ids: tuple[str, ...] = Field(min_length=1)
    guidance_query: KnowledgeRetrievalQuery
    expected_retrieval_ids: tuple[str, ...] = Field(min_length=1)
    exposed_api_methods: tuple[str, ...] = ("GET",)
    identity_owner: str = "application"
    scoring_authority_preserved: bool = True
    planner_authority_preserved: bool = True
    memory_authority_preserved: bool = True
    agent_authority_preserved: bool = True
    practice_target_authority_preserved: bool = True


def evaluate_wiki_knowledge(
    evidence: WikiEvalEvidence,
    *,
    pages: Sequence[WikiPage] = WIKI_PAGES,
    relations: Sequence[WikiRelation] = WIKI_RELATIONS,
    knowledge_units: Sequence[KnowledgeUnit] = WRITING_TASK2_KNOWLEDGE_UNITS,
    sources: Mapping[str, KnowledgeSource] = KNOWLEDGE_SOURCES,
) -> EvalFinding:
    """Verify the canonical Wiki and its guidance bridge without provider access."""

    try:
        validate_wiki_snapshot(
            pages=pages,
            relations=relations,
            knowledge_units=knowledge_units,
            sources=sources,
        )
    except WikiIntegrityError:
        return _failure("wiki_snapshot_integrity")

    counts = Counter(relation.relation_type for relation in relations)
    if (
        len(pages) != 58
        or len(knowledge_units) != 54
        or len(relations) != 93
        or counts[WikiRelationType.CONTAINS] != 57
        or counts[WikiRelationType.ADJACENT_BAND] != 36
        or any(
            relation.authority is not WikiRelationAuthority.APPLICATION_STRUCTURAL
            for relation in relations
        )
    ):
        return _failure("wiki_canonical_inventory_mismatch")

    if any(
        re.fullmatch(WIKI_PAGE_ID_PATTERN, page.page_id) is None for page in pages
    ):
        return _failure("wiki_page_identity_invalid")

    index = WIKI_SERVICE.index()
    if tuple(page.page_id for page in index.pages) != tuple(page.page_id for page in pages):
        return _failure("wiki_preorder_not_deterministic")

    for page in pages:
        if WIKI_SERVICE.resolve_identity(page.title).page_id != page.page_id:
            return _failure("wiki_title_lookup_mismatch")
        detail = WIKI_SERVICE.detail(page)
        if not detail.breadcrumbs or detail.breadcrumbs[-1].page_id != page.page_id:
            return _failure("wiki_breadcrumb_mismatch")
        expected_relations = tuple(
            relation
            for relation in relations
            if page.page_id in (relation.source_page_id, relation.target_page_id)
        )
        observed_relations = tuple(
            (relation.relation_type, relation.source_page_id, relation.target_page_id)
            for relation in detail.relations
        )
        if observed_relations != tuple(
            (relation.relation_type, relation.source_page_id, relation.target_page_id)
            for relation in expected_relations
        ):
            return _failure("wiki_incident_relation_mismatch")
        expected_neighbors = _expected_neighbors_for_page(page, pages, relations)
        observed_neighbors = _neighbor_semantics(WIKI_SERVICE.neighbors(page))
        if observed_neighbors != expected_neighbors:
            return _failure("wiki_neighbor_projection_mismatch")
        if observed_neighbors != _neighbor_semantics(WIKI_SERVICE.neighbors(page)):
            return _failure("wiki_neighbor_not_deterministic")
        for projection in detail.knowledge:
            unit = next(
                (item for item in knowledge_units if item.knowledge_id == projection.knowledge_id),
                None,
            )
            if unit is None or tuple(
                (source.source_id, source.locator, source.page, source.section)
                for source in projection.sources
            ) != tuple(
                (reference.source_id, reference.locator, reference.page, reference.section)
                for reference in unit.source_refs
            ):
                return _failure("wiki_provenance_mismatch")

    try:
        WIKI_SERVICE.get_page("writing-task2-unknown")
    except WikiPageNotFoundError:
        pass
    else:
        return _failure("wiki_unknown_page_not_fail_closed")
    try:
        WIKI_SERVICE.page_for_knowledge_id("unknown-knowledge-id")
    except WikiPageNotFoundError:
        pass
    else:
        return _failure("wiki_unknown_knowledge_not_fail_closed")

    resolved_pages: list[str] = []
    for knowledge_id in evidence.guidance_knowledge_ids:
        try:
            page_id = WIKI_SERVICE.page_for_knowledge_id(knowledge_id).page_id
        except WikiPageNotFoundError:
            return _failure("wiki_guidance_unknown_knowledge")
        if page_id not in resolved_pages:
            resolved_pages.append(page_id)
    if tuple(resolved_pages) != evidence.guidance_page_ids:
        return _failure("wiki_guidance_bridge_mismatch")

    first = tuple(
        unit.knowledge_id for unit in retrieve_knowledge(evidence.guidance_query).units
    )
    second = tuple(
        unit.knowledge_id for unit in retrieve_knowledge(evidence.guidance_query).units
    )
    if first != second or first != evidence.expected_retrieval_ids:
        return _failure("wiki_changed_adaptive_retrieval", EvalSeverity.VETO)

    if evidence.exposed_api_methods != ("GET",):
        return _failure("wiki_mutation_api_exposed")
    if evidence.identity_owner != "application":
        return _failure("wiki_provider_identity_authority")
    if not all(
        (
            evidence.scoring_authority_preserved,
            evidence.planner_authority_preserved,
            evidence.memory_authority_preserved,
            evidence.agent_authority_preserved,
            evidence.practice_target_authority_preserved,
        )
    ):
        return _failure("wiki_authority_boundary_changed")

    return EvalFinding(
        evaluator=EvaluatorId.WIKI_KNOWLEDGE,
        status=EvalStatus.PASS,
        severity=EvalSeverity.INFO,
    )


def _expected_neighbors_for_page(
    page: WikiPage,
    pages: Sequence[WikiPage],
    relations: Sequence[WikiRelation],
) -> tuple[NeighborSemantic, ...]:
    """Derive the frozen neighbor projection without using WikiService."""

    page_by_id = {candidate.page_id: candidate for candidate in pages}
    page_order = {
        candidate.page_id: index for index, candidate in enumerate(pages)
    }
    buckets: dict[WikiNeighborDirection, list[NeighborSemantic]] = {
        direction: [] for direction in WikiNeighborDirection
    }

    def append_neighbor(
        page_id: str,
        relation_type: WikiRelationType,
        direction: WikiNeighborDirection,
    ) -> None:
        neighbor = page_by_id[page_id]
        buckets[direction].append(
            (
                neighbor.page_id,
                neighbor.page_type,
                neighbor.title,
                relation_type,
                direction,
            )
        )

    for relation in relations:
        if relation.relation_type is WikiRelationType.CONTAINS:
            if relation.source_page_id == page.page_id:
                append_neighbor(
                    relation.target_page_id,
                    relation.relation_type,
                    WikiNeighborDirection.CHILD,
                )
            elif relation.target_page_id == page.page_id:
                append_neighbor(
                    relation.source_page_id,
                    relation.relation_type,
                    WikiNeighborDirection.PARENT,
                )
        elif relation.relation_type is WikiRelationType.ADJACENT_BAND:
            if relation.source_page_id == page.page_id:
                append_neighbor(
                    relation.target_page_id,
                    relation.relation_type,
                    WikiNeighborDirection.NEXT_BAND,
                )
            elif relation.target_page_id == page.page_id:
                append_neighbor(
                    relation.source_page_id,
                    relation.relation_type,
                    WikiNeighborDirection.PREVIOUS_BAND,
                )

    for neighbors in buckets.values():
        neighbors.sort(key=lambda neighbor: page_order[neighbor[0]])
    return tuple(
        neighbor
        for direction in (
            WikiNeighborDirection.PARENT,
            WikiNeighborDirection.CHILD,
            WikiNeighborDirection.PREVIOUS_BAND,
            WikiNeighborDirection.NEXT_BAND,
        )
        for neighbor in buckets[direction]
    )


def _neighbor_semantics(
    neighbors: Sequence[WikiNeighborView],
) -> tuple[NeighborSemantic, ...]:
    return tuple(
        (
            neighbor.page_id,
            neighbor.page_type,
            neighbor.title,
            neighbor.relation_type,
            neighbor.direction,
        )
        for neighbor in neighbors
    )


def _failure(code: str, severity: EvalSeverity = EvalSeverity.VETO) -> EvalFinding:
    return EvalFinding(
        evaluator=EvaluatorId.WIKI_KNOWLEDGE,
        status=EvalStatus.FAIL,
        severity=severity,
        first_failing_boundary=FailureBoundary.KNOWLEDGE,
        failure_codes=(code,),
    )


__all__ = ["WikiEvalEvidence", "evaluate_wiki_knowledge"]
