"""Thin read-only HTTP routes for the canonical Writing Wiki."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.schemas.wiki import (
    WIKI_PAGE_ID_PATTERN,
    WikiIndexResponse,
    WikiPageDetail,
)
from app.wiki.service import WikiService, get_wiki_service


router = APIRouter(prefix="/knowledge/writing/wiki", tags=["wiki"])


@router.get("", response_model=WikiIndexResponse | WikiPageDetail)
def get_wiki_index(
    service: Annotated[WikiService, Depends(get_wiki_service)],
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> WikiIndexResponse | WikiPageDetail:
    if q is None:
        return service.index()
    return service.detail(service.resolve_identity(q))


@router.get("/{page_id}", response_model=WikiPageDetail)
def get_wiki_page(
    page_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=128,
            pattern=WIKI_PAGE_ID_PATTERN,
        ),
    ],
    service: Annotated[WikiService, Depends(get_wiki_service)],
) -> WikiPageDetail:
    return service.detail(page_id)
