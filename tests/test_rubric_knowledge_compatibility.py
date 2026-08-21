from app.evaluators.rubrics.writing_task2_v1 import (
    WRITING_TASK2_BAND_DESCRIPTORS,
    WRITING_TASK2_RUBRIC_VERSION,
)
from app.knowledge.rubric_compatibility import (
    RUBRIC_KNOWLEDGE_MAP,
    RubricCompatibilityStatus,
    audit_writing_task2_rubric,
)
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS


def test_every_existing_rubric_criterion_and_integer_band_is_audited() -> None:
    audit = audit_writing_task2_rubric()
    assert WRITING_TASK2_RUBRIC_VERSION == "writing-task2-v1"
    assert set(audit) == set(WRITING_TASK2_BAND_DESCRIPTORS)
    assert all(set(audit[criterion]) == set(range(10)) for criterion in audit)
    assert all(status is RubricCompatibilityStatus.COMPATIBLE_WITH_MISSING_PROVENANCE for bands in audit.values() for status in bands.values())


def test_all_audit_mappings_resolve_to_static_official_knowledge() -> None:
    identifiers = {unit.knowledge_id for unit in WRITING_TASK2_KNOWLEDGE_UNITS}
    assert all(identifier in identifiers for bands in RUBRIC_KNOWLEDGE_MAP.values() for mapped in bands.values() for identifier in mapped)
