"""Registered official sources for the immutable Phase 9 snapshot."""

from types import MappingProxyType
from typing import Final, Mapping

from app.schemas.knowledge import (
    KnowledgeAuthority,
    KnowledgeSource,
    KnowledgeSourceType,
)


KNOWLEDGE_SOURCES: Final[Mapping[str, KnowledgeSource]] = MappingProxyType(
    {
        "ielts-writing-band-descriptors-2023": KnowledgeSource(
            source_id="ielts-writing-band-descriptors-2023",
            authority=KnowledgeAuthority.OFFICIAL_IELTS,
            publisher="IELTS",
            title="IELTS Writing Band Descriptors",
            url="https://ielts.org/cdn/ielts-guides/ielts-writing-band-descriptors.pdf",
            source_type=KnowledgeSourceType.OFFICIAL_WEB_OR_PDF,
            verified_at="2026-08-21",
            source_revision="2023-05",
        ),
        "ielts-writing-key-assessment-criteria": KnowledgeSource(
            source_id="ielts-writing-key-assessment-criteria",
            authority=KnowledgeAuthority.OFFICIAL_IELTS,
            publisher="IELTS",
            title="IELTS Writing Key Assessment Criteria",
            url="https://ielts.org/cdn/ielts-guides/ielts-writing-key-assessment-criteria.pdf",
            source_type=KnowledgeSourceType.OFFICIAL_WEB_OR_PDF,
            verified_at="2026-08-21",
        ),
        "ielts-writing-task2-question-prompts-2023": KnowledgeSource(
            source_id="ielts-writing-task2-question-prompts-2023",
            authority=KnowledgeAuthority.OFFICIAL_IELTS,
            publisher="IELTS",
            title="IELTS Writing Task 2: How to understand IELTS question prompts",
            url="https://ielts.org/news-and-insights/ielts-writing-task-2-how-to-understand-ielts-question-prompts",
            source_type=KnowledgeSourceType.OFFICIAL_WEB_OR_PDF,
            verified_at="2026-08-21",
            source_revision="2023-02-01",
        ),
        "ielts-academic-writing-format": KnowledgeSource(
            source_id="ielts-academic-writing-format",
            authority=KnowledgeAuthority.OFFICIAL_IELTS,
            publisher="IELTS",
            title="IELTS Academic: Writing test format",
            url="https://ielts.org/take-a-test/test-types/ielts-academic-test/ielts-academic-format-writing",
            source_type=KnowledgeSourceType.OFFICIAL_WEB_OR_PDF,
            verified_at="2026-08-21",
        ),
    }
)
