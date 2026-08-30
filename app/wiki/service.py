"""Provider-free deterministic navigation and projection for the Writing Wiki."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.schemas.knowledge import KnowledgeSource, KnowledgeUnit
from app.schemas.wiki import (
    WIKI_ROOT_PAGE_ID,
    WikiBreadcrumb,
    WikiIndexResponse,
    WikiKnowledgeProjection,
    WikiNeighborDirection,
    WikiNeighborView,
    WikiPage,
    WikiPageDetail,
    WikiPageSummary,
    WikiRelation,
    WikiRelationType,
    WikiRelationView,
    WikiSourceProjection,
)
from app.wiki.errors import (
    WikiLookupAmbiguousError,
    WikiPageNotFoundError,
    WikiUnavailableError,
)
from app.wiki.identity import normalize_wiki_identity
from app.wiki.snapshot import VALIDATED_WIKI_SNAPSHOT, ValidatedWikiSnapshot


class WikiService:
    """Read-only access over one already validated immutable snapshot."""

    def __init__(
        self,
        snapshot: ValidatedWikiSnapshot = VALIDATED_WIKI_SNAPSHOT,
    ) -> None:
        self._pages = snapshot.pages
        self._relations = snapshot.relations
        self._page_by_id = {page.page_id: page for page in snapshot.pages}
        self._knowledge_by_id = {
            unit.knowledge_id: unit for unit in snapshot.knowledge_units
        }
        self._sources = snapshot.sources
        self._page_by_knowledge_id = {
            knowledge_id: page
            for page in snapshot.pages
            for knowledge_id in page.knowledge_ids
        }
        self._title_index = self._identity_index(
            (page.title, page) for page in snapshot.pages
        )
        self._alias_index = self._identity_index(
            (alias, page) for page in snapshot.pages for alias in page.aliases
        )

    @staticmethod
    def _identity_index(
        values: Iterable[tuple[str, WikiPage]],
    ) -> dict[str, tuple[WikiPage, ...]]:
        grouped: dict[str, list[WikiPage]] = defaultdict(list)
        for identity, page in values:
            grouped[normalize_wiki_identity(identity)].append(page)
        return {identity: tuple(pages) for identity, pages in grouped.items()}

    @staticmethod
    def _summary(page: WikiPage) -> WikiPageSummary:
        return WikiPageSummary(
            page_id=page.page_id,
            page_type=page.page_type,
            title=page.title,
            aliases=page.aliases,
            parent_page_id=page.parent_page_id,
            order=page.order,
            has_knowledge=bool(page.knowledge_ids),
        )

    def index(self) -> WikiIndexResponse:
        return WikiIndexResponse(
            root_page_id=WIKI_ROOT_PAGE_ID,
            pages=tuple(self._summary(page) for page in self._pages),
        )

    def get_page(self, page_id: str) -> WikiPage:
        page = self._page_by_id.get(page_id)
        if page is None:
            raise WikiPageNotFoundError("wiki page was not found")
        return page

    def resolve_identity(self, identity: str) -> WikiPage:
        exact = self._page_by_id.get(identity)
        if exact is not None:
            return exact
        normalized = normalize_wiki_identity(identity)
        title_matches = self._title_index.get(normalized, ())
        if title_matches:
            return self._one_match(title_matches)
        alias_matches = self._alias_index.get(normalized, ())
        if alias_matches:
            return self._one_match(alias_matches)
        raise WikiPageNotFoundError("wiki page was not found")

    @staticmethod
    def _one_match(matches: tuple[WikiPage, ...]) -> WikiPage:
        if len(matches) != 1:
            raise WikiLookupAmbiguousError("wiki lookup is ambiguous")
        return matches[0]

    def page_for_knowledge_id(self, knowledge_id: str) -> WikiPage:
        page = self._page_by_knowledge_id.get(knowledge_id)
        if page is None:
            raise WikiPageNotFoundError("wiki page was not found")
        return page

    def breadcrumbs(self, page: WikiPage) -> tuple[WikiBreadcrumb, ...]:
        chain: list[WikiPage] = []
        current: WikiPage | None = page
        while current is not None:
            chain.append(current)
            current = (
                self._page_by_id[current.parent_page_id]
                if current.parent_page_id is not None
                else None
            )
        chain.reverse()
        return tuple(
            WikiBreadcrumb(page_id=item.page_id, title=item.title) for item in chain
        )

    def children(self, page: WikiPage) -> tuple[WikiPage, ...]:
        return tuple(
            candidate
            for candidate in self._pages
            if candidate.parent_page_id == page.page_id
        )

    def incident_relations(self, page: WikiPage) -> tuple[WikiRelation, ...]:
        return tuple(
            relation
            for relation in self._relations
            if relation.source_page_id == page.page_id
            or relation.target_page_id == page.page_id
        )

    def neighbors(self, page: WikiPage) -> tuple[WikiNeighborView, ...]:
        incident = self.incident_relations(page)
        parent: list[WikiNeighborView] = []
        children: list[WikiNeighborView] = []
        previous: list[WikiNeighborView] = []
        following: list[WikiNeighborView] = []
        for relation in incident:
            if relation.relation_type is WikiRelationType.CONTAINS:
                if relation.target_page_id == page.page_id:
                    parent.append(
                        self._neighbor(
                            relation.source_page_id,
                            relation.relation_type,
                            WikiNeighborDirection.PARENT,
                        )
                    )
                else:
                    children.append(
                        self._neighbor(
                            relation.target_page_id,
                            relation.relation_type,
                            WikiNeighborDirection.CHILD,
                        )
                    )
            elif relation.target_page_id == page.page_id:
                previous.append(
                    self._neighbor(
                        relation.source_page_id,
                        relation.relation_type,
                        WikiNeighborDirection.PREVIOUS_BAND,
                    )
                )
            else:
                following.append(
                    self._neighbor(
                        relation.target_page_id,
                        relation.relation_type,
                        WikiNeighborDirection.NEXT_BAND,
                    )
                )
        children.sort(key=lambda item: self._page_by_id[item.page_id].order)
        return tuple(parent + children + previous + following)

    def _neighbor(
        self,
        page_id: str,
        relation_type: WikiRelationType,
        direction: WikiNeighborDirection,
    ) -> WikiNeighborView:
        page = self._page_by_id[page_id]
        return WikiNeighborView(
            page_id=page.page_id,
            page_type=page.page_type,
            title=page.title,
            relation_type=relation_type,
            direction=direction,
        )

    def _source_projection(
        self, unit: KnowledgeUnit
    ) -> tuple[WikiSourceProjection, ...]:
        projections: list[WikiSourceProjection] = []
        seen: set[tuple[str, str, int | None, str | None]] = set()
        for reference in unit.source_refs:
            key = (
                reference.source_id,
                reference.locator,
                reference.page,
                reference.section,
            )
            if key in seen:
                continue
            seen.add(key)
            source: KnowledgeSource | None = self._sources.get(reference.source_id)
            if source is None:
                raise WikiUnavailableError("wiki provenance is unavailable")
            projections.append(
                WikiSourceProjection(
                    source_id=source.source_id,
                    authority=source.authority,
                    publisher=source.publisher,
                    title=source.title,
                    url=source.url,
                    source_type=source.source_type,
                    verified_at=source.verified_at,
                    source_revision=source.source_revision,
                    locator=reference.locator,
                    page=reference.page,
                    section=reference.section,
                )
            )
        return tuple(projections)

    def knowledge_projection(
        self, page: WikiPage
    ) -> tuple[WikiKnowledgeProjection, ...]:
        projections: list[WikiKnowledgeProjection] = []
        for knowledge_id in page.knowledge_ids:
            unit = self._knowledge_by_id.get(knowledge_id)
            if unit is None:
                raise WikiUnavailableError("wiki knowledge is unavailable")
            projections.append(
                WikiKnowledgeProjection(
                    knowledge_id=unit.knowledge_id,
                    knowledge_version=unit.knowledge_version,
                    task=unit.task,
                    category=unit.category,
                    statement=unit.statement,
                    criterion=unit.criterion,
                    descriptor_band=unit.descriptor_band,
                    task_type=unit.task_type,
                    sources=self._source_projection(unit),
                )
            )
        return tuple(projections)

    def detail(self, page: WikiPage | str) -> WikiPageDetail:
        resolved = self.get_page(page) if isinstance(page, str) else page
        return WikiPageDetail(
            page=self._summary(resolved),
            breadcrumbs=self.breadcrumbs(resolved),
            knowledge=self.knowledge_projection(resolved),
            children=tuple(self._summary(child) for child in self.children(resolved)),
            relations=tuple(
                WikiRelationView.model_validate(relation.model_dump())
                for relation in self.incident_relations(resolved)
            ),
            neighbors=self.neighbors(resolved),
        )


WIKI_SERVICE = WikiService()


def get_wiki_service() -> WikiService:
    """Return the validated immutable Wiki singleton for dependency injection."""
    return WIKI_SERVICE
