"""Application-safe validated Wiki singleton boundary."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from app.schemas.knowledge import KnowledgeSource, KnowledgeUnit
from app.schemas.wiki import WikiPage, WikiRelation
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.wiki.registry import WIKI_PAGES
from app.wiki.relations import WIKI_RELATIONS
from app.wiki.validation import validate_wiki_snapshot


@dataclass(frozen=True, slots=True)
class ValidatedWikiSnapshot:
    pages: tuple[WikiPage, ...]
    relations: tuple[WikiRelation, ...]
    knowledge_units: tuple[KnowledgeUnit, ...]
    sources: Mapping[str, KnowledgeSource]


validate_wiki_snapshot()

VALIDATED_WIKI_SNAPSHOT: Final = ValidatedWikiSnapshot(
    pages=WIKI_PAGES,
    relations=WIKI_RELATIONS,
    knowledge_units=WRITING_TASK2_KNOWLEDGE_UNITS,
    sources=MappingProxyType(dict(KNOWLEDGE_SOURCES)),
)
