from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS, validate_snapshot_integrity
from app.schemas.knowledge import KnowledgeAuthority, KnowledgeCategory


def test_official_snapshot_has_stable_unique_ids_and_resolving_provenance() -> None:
    validate_snapshot_integrity()
    assert len(KNOWLEDGE_SOURCES) == len(set(KNOWLEDGE_SOURCES))
    assert all(source.authority is KnowledgeAuthority.OFFICIAL_IELTS for source in KNOWLEDGE_SOURCES.values())
    ids = [unit.knowledge_id for unit in WRITING_TASK2_KNOWLEDGE_UNITS]
    assert len(ids) == len(set(ids))
    assert all(reference.source_id in KNOWLEDGE_SOURCES for unit in WRITING_TASK2_KNOWLEDGE_UNITS for reference in unit.source_refs)


def test_snapshot_covers_all_criteria_and_integer_descriptor_bands() -> None:
    criteria = (
        "task_response", "coherence_and_cohesion", "lexical_resource", "grammatical_range_and_accuracy",
    )
    for criterion in criteria:
        bands = {unit.descriptor_band for unit in WRITING_TASK2_KNOWLEDGE_UNITS if unit.criterion == criterion and unit.category is KnowledgeCategory.BAND_GUIDANCE}
        assert bands == set(range(10))
    assert all(unit.descriptor_band is None or isinstance(unit.descriptor_band, int) for unit in WRITING_TASK2_KNOWLEDGE_UNITS)


def test_snapshot_contains_rules_and_canonical_task_types() -> None:
    rules = [unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS if unit.category is KnowledgeCategory.TASK_RULE]
    task_types = [unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS if unit.category is KnowledgeCategory.TASK_UNDERSTANDING]
    assert len(rules) >= 3
    assert {unit.task_type.value for unit in task_types} == {
        "opinion", "discussion", "multi_part", "multi_part_opinion", "advantage_disadvantage", "positive_negative", "cause_solution",
    }
