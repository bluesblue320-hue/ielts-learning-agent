"""Semantic and provenance invariants for the repaired descriptor snapshot."""

import pytest

from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.knowledge import KnowledgeCategory


_CRITERION_LABELS = {
    "task_response": "Task Response",
    "coherence_and_cohesion": "Coherence and Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_and_accuracy": "Grammatical Range and Accuracy",
}

_BAND_SEVEN_SEMANTIC_MARKERS = {
    "task_response": ("task parts", "position", "support"),
    "coherence_and_cohesion": ("progression", "paragraphing", "cohesion"),
    "lexical_resource": ("vocabulary", "less-common", "collocation"),
    "grammatical_range_and_accuracy": (
        "complex structures",
        "grammatical",
        "punctuation",
    ),
}


def _descriptors():
    return tuple(
        unit
        for unit in WRITING_TASK2_KNOWLEDGE_UNITS
        if unit.category is KnowledgeCategory.BAND_GUIDANCE
    )


def test_snapshot_has_exactly_four_complete_integer_descriptor_series() -> None:
    descriptors = _descriptors()

    assert len(descriptors) == 40
    assert all(isinstance(unit.descriptor_band, int) for unit in descriptors)
    for criterion in _CRITERION_LABELS:
        criterion_units = tuple(
            unit for unit in descriptors if unit.criterion == criterion
        )
        assert len(criterion_units) == 10
        assert {unit.descriptor_band for unit in criterion_units} == set(range(10))
        assert {
            unit.knowledge_id for unit in criterion_units
        } == {
            f"writing-{criterion.replace('_', '-')}-band-{band}"
            for band in range(10)
        }


def test_every_descriptor_has_aligned_official_claim_provenance() -> None:
    for unit in _descriptors():
        assert unit.descriptor_band is not None
        assert unit.criterion is not None
        assert len(unit.source_refs) == 1
        reference = unit.source_refs[0]
        label = _CRITERION_LABELS[unit.criterion]

        assert reference.source_id == "ielts-writing-band-descriptors-2023"
        assert reference.source_id in KNOWLEDGE_SOURCES
        assert reference.locator.strip()
        assert reference.locator == (
            f"Writing Task 2 / {label} / Band {unit.descriptor_band}"
        )
        assert reference.section == label


def test_same_band_preserves_each_criterion_specific_semantics() -> None:
    band_seven = {
        unit.criterion: unit.statement.lower()
        for unit in _descriptors()
        if unit.descriptor_band == 7
    }

    assert len(set(band_seven.values())) == 4
    for criterion, markers in _BAND_SEVEN_SEMANTIC_MARKERS.items():
        assert all(marker in band_seven[criterion] for marker in markers)


@pytest.mark.parametrize(
    ("criterion", "band", "required", "forbidden"),
    (
        (
            "task_response",
            5,
            ("incomplete", "unclear", "underdeveloped"),
            ("requirements are covered", "generally addressed"),
        ),
        (
            "coherence_and_cohesion",
            6,
            ("progression", "mechanical", "illogical"),
            ("consistently logical", "paragraphing is logical"),
        ),
        (
            "lexical_resource",
            5,
            ("limited", "minimally adequate", "errors"),
            ("range is adequate", "flexible"),
        ),
        (
            "lexical_resource",
            6,
            ("adequate", "restricted", "imprecise"),
            ("varied", "flexible"),
        ),
    ),
)
def test_official_source_calibration_preserves_adjacent_band_limitations(
    criterion: str,
    band: int,
    required: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> None:
    statement = next(
        unit.statement.lower()
        for unit in _descriptors()
        if unit.criterion == criterion and unit.descriptor_band == band
    )

    assert all(marker in statement for marker in required)
    assert all(overstatement not in statement for overstatement in forbidden)
