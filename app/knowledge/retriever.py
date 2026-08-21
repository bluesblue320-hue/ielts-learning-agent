"""Provider-free deterministic retrieval over the checked-in v1 snapshot."""

from __future__ import annotations

from decimal import Decimal

from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS, validate_snapshot_integrity
from app.schemas.knowledge import (
    KnowledgeCategory,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
    KnowledgeRetrievalResult,
    KnowledgeUnit,
)


MAX_RESULTS_BY_PURPOSE = {
    KnowledgeRetrievalPurpose.PRACTICE_GENERATION: 7,
    KnowledgeRetrievalPurpose.LEARNER_GUIDANCE: 8,
    KnowledgeRetrievalPurpose.RUBRIC_COMPATIBILITY: 2,
}


def descriptor_bands(value: Decimal) -> tuple[int, ...]:
    """Map a validated product half-band to official integer descriptors."""
    lower = int(value)
    if value == Decimal("9.0") or value == Decimal(lower):
        return (lower,)
    return (lower, lower + 1)


def _units_for(query: KnowledgeRetrievalQuery) -> tuple[KnowledgeUnit, ...]:
    criterion_units = tuple(
        unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS if unit.criterion == query.criterion
    )
    if query.purpose is KnowledgeRetrievalPurpose.RUBRIC_COMPATIBILITY:
        assert query.current_band is not None
        needed_bands = descriptor_bands(query.current_band.value)
    elif query.purpose is KnowledgeRetrievalPurpose.PRACTICE_GENERATION:
        assert query.target_band is not None
        needed_bands = descriptor_bands(query.target_band.value)
    else:
        assert query.current_band is not None and query.target_band is not None
        needed_bands = descriptor_bands(query.current_band.value) + descriptor_bands(query.target_band.value)

    descriptor = tuple(
        unit for unit in criterion_units
        if unit.category is KnowledgeCategory.BAND_GUIDANCE and unit.descriptor_band in needed_bands
    )
    criterion_general = tuple(
        unit for unit in criterion_units if unit.category is KnowledgeCategory.ASSESSMENT
    )
    rules = tuple(unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS if unit.category is KnowledgeCategory.TASK_RULE)
    task_type = tuple(
        unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS
        if unit.category is KnowledgeCategory.TASK_UNDERSTANDING and unit.task_type == query.task_type
    )
    if query.purpose is KnowledgeRetrievalPurpose.RUBRIC_COMPATIBILITY:
        return descriptor
    return descriptor + criterion_general + task_type + rules


def retrieve_knowledge(query: KnowledgeRetrievalQuery) -> KnowledgeRetrievalResult:
    """Return a bounded declaration-order result for a closed structured query."""
    validate_snapshot_integrity()
    limit = MAX_RESULTS_BY_PURPOSE[query.purpose]
    ordered: list[KnowledgeUnit] = []
    seen: set[str] = set()
    for unit in _units_for(query):
        if unit.knowledge_id not in seen:
            seen.add(unit.knowledge_id)
            ordered.append(unit)
        if len(ordered) == limit:
            break
    return KnowledgeRetrievalResult(query=query, units=tuple(ordered))
