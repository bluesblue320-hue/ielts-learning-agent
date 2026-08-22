from collections import Counter
from dataclasses import replace
from hashlib import sha256

import pytest

from app.evaluators.rubrics.writing_task2_v1 import (
    WRITING_TASK2_BAND_DESCRIPTORS,
    WRITING_TASK2_RUBRIC_VERSION,
)
from app.knowledge.rubric_compatibility import (
    RUBRIC_COMPATIBILITY_LEDGER,
    RUBRIC_KNOWLEDGE_MAP,
    RubricCompatibilityStatus,
    audit_writing_task2_rubric,
    validate_rubric_compatibility_ledger,
)
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.writing import WritingCriterion


def test_all_40_rubric_anchors_have_unique_explicit_reviewed_entries() -> None:
    entries = RUBRIC_COMPATIBILITY_LEDGER
    keys = {(entry.criterion, entry.band) for entry in entries}

    assert WRITING_TASK2_RUBRIC_VERSION == "writing-task2-v1"
    assert len(entries) == 40
    assert len(keys) == 40
    assert keys == {
        (criterion, band)
        for criterion in WritingCriterion
        for band in range(10)
    }
    assert all(entry.knowledge_ids for entry in entries)
    assert all(entry.rationale.strip() for entry in entries)
    assert all(isinstance(entry.compatibility_status, RubricCompatibilityStatus) for entry in entries)


def test_all_reviewed_knowledge_references_resolve_and_align() -> None:
    units = {unit.knowledge_id: unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS}
    validate_rubric_compatibility_ledger()

    for entry in RUBRIC_COMPATIBILITY_LEDGER:
        assert RUBRIC_KNOWLEDGE_MAP[entry.criterion][entry.band] == entry.knowledge_ids
        for knowledge_id in entry.knowledge_ids:
            unit = units[knowledge_id]
            assert unit.criterion == entry.criterion.value
            assert unit.descriptor_band == entry.band


@pytest.mark.parametrize(
    "invalid_ledger",
    [
        RUBRIC_COMPATIBILITY_LEDGER[:-1],
        (*RUBRIC_COMPATIBILITY_LEDGER[:-1], RUBRIC_COMPATIBILITY_LEDGER[0]),
        (*RUBRIC_COMPATIBILITY_LEDGER, RUBRIC_COMPATIBILITY_LEDGER[0]),
    ],
    ids=["missing", "duplicate", "extra"],
)
def test_invalid_ledger_cardinality_or_identity_fails_closed(invalid_ledger: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        validate_rubric_compatibility_ledger(invalid_ledger)  # type: ignore[arg-type]


def test_unknown_knowledge_reference_fails_closed() -> None:
    changed = replace(
        RUBRIC_COMPATIBILITY_LEDGER[0],
        knowledge_ids=("unknown-knowledge-id",),
    )
    with pytest.raises(ValueError, match="does not resolve"):
        validate_rubric_compatibility_ledger((changed, *RUBRIC_COMPATIBILITY_LEDGER[1:]))


def test_blank_rationale_and_invalid_status_fail_closed() -> None:
    blank = replace(RUBRIC_COMPATIBILITY_LEDGER[0], rationale="   ")
    with pytest.raises(ValueError, match="rationale"):
        validate_rubric_compatibility_ledger((blank, *RUBRIC_COMPATIBILITY_LEDGER[1:]))

    invalid_status = replace(
        RUBRIC_COMPATIBILITY_LEDGER[0],
        compatibility_status="compatible",  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="status"):
        validate_rubric_compatibility_ledger((invalid_status, *RUBRIC_COMPATIBILITY_LEDGER[1:]))


def test_id_existence_alone_cannot_create_a_compatibility_result() -> None:
    same_id_but_unreviewed_text = replace(
        RUBRIC_COMPATIBILITY_LEDGER[0],
        knowledge_statement_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="Knowledge wording"):
        audit_writing_task2_rubric(
            (same_id_but_unreviewed_text, *RUBRIC_COMPATIBILITY_LEDGER[1:])
        )

    changed_rubric_identity = replace(
        RUBRIC_COMPATIBILITY_LEDGER[0],
        rubric_anchor_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="rubric wording"):
        audit_writing_task2_rubric(
            (changed_rubric_identity, *RUBRIC_COMPATIBILITY_LEDGER[1:])
        )


def test_runtime_audit_returns_the_status_declared_by_the_ledger() -> None:
    reviewed_as_compatible = replace(
        RUBRIC_COMPATIBILITY_LEDGER[0],
        compatibility_status=RubricCompatibilityStatus.COMPATIBLE,
    )
    ledger = (reviewed_as_compatible, *RUBRIC_COMPATIBILITY_LEDGER[1:])

    audit = audit_writing_task2_rubric(ledger)

    assert set(audit) == set(WRITING_TASK2_BAND_DESCRIPTORS)
    assert audit[reviewed_as_compatible.criterion][0] is RubricCompatibilityStatus.COMPATIBLE
    assert audit[WritingCriterion.TASK_RESPONSE][1] is RubricCompatibilityStatus.COMPATIBLE_WITH_MISSING_PROVENANCE


_DOCUMENTED_GAPS = {
    (WritingCriterion.TASK_RESPONSE, band) for band in range(3, 9)
} | {
    (WritingCriterion.COHERENCE_AND_COHESION, band) for band in range(3, 9)
} | {
    (WritingCriterion.LEXICAL_RESOURCE, band) for band in range(4, 8)
} | {
    (WritingCriterion.GRAMMATICAL_RANGE_AND_ACCURACY, 4)
}


def test_all_40_reviewed_hashes_match_current_knowledge_statements() -> None:
    units = {unit.knowledge_id: unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS}

    for entry in RUBRIC_COMPATIBILITY_LEDGER:
        statements = "\n".join(
            units[knowledge_id].statement for knowledge_id in entry.knowledge_ids
        )
        assert entry.knowledge_statement_sha256 == sha256(
            statements.encode("utf-8")
        ).hexdigest()


def test_reviewed_status_distribution_and_all_documented_gaps_are_preserved() -> None:
    status_by_key = {
        (entry.criterion, entry.band): entry.compatibility_status
        for entry in RUBRIC_COMPATIBILITY_LEDGER
    }

    assert {
        key
        for key, status in status_by_key.items()
        if status is RubricCompatibilityStatus.GAP_REQUIRES_DOCUMENTATION
    } == _DOCUMENTED_GAPS
    assert Counter(status_by_key.values()) == {
        RubricCompatibilityStatus.COMPATIBLE_WITH_MISSING_PROVENANCE: 23,
        RubricCompatibilityStatus.GAP_REQUIRES_DOCUMENTATION: 17,
    }

    audit = audit_writing_task2_rubric()
    for criterion, band in _DOCUMENTED_GAPS:
        assert audit[criterion][band] is RubricCompatibilityStatus.GAP_REQUIRES_DOCUMENTATION
