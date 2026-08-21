"""Deterministic provenance audit for the frozen writing-task2-v1 rubric."""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Final, Mapping

from app.evaluators.rubrics.writing_task2_v1 import WRITING_TASK2_BAND_DESCRIPTORS
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.writing import WritingCriterion


class RubricCompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_MISSING_PROVENANCE = "compatible_with_missing_provenance"
    GAP_REQUIRES_DOCUMENTATION = "gap_requires_documentation"
    MATERIAL_CONFLICT = "material_conflict"


RUBRIC_KNOWLEDGE_MAP: Final[Mapping[WritingCriterion, Mapping[int, tuple[str, ...]]]] = MappingProxyType(
    {
        criterion: MappingProxyType(
            {
                band: (f"writing-{criterion.value.replace('_', '-')}-band-{band}",)
                for band in range(10)
            }
        )
        for criterion in WritingCriterion
    }
)


def audit_writing_task2_rubric() -> Mapping[WritingCriterion, Mapping[int, RubricCompatibilityStatus]]:
    """Audit coverage and source resolution without changing score semantics.

    Existing v1 wording is a product-owned, concise rubric and did not store
    official claim provenance.  Its dimensions and integer-band coverage align
    with the static official snapshot, so every entry is explicitly recorded as
    compatible while retaining the missing-historical-provenance caveat.
    """
    snapshot_ids = {unit.knowledge_id for unit in WRITING_TASK2_KNOWLEDGE_UNITS}
    results: dict[WritingCriterion, Mapping[int, RubricCompatibilityStatus]] = {}
    for criterion, descriptors in WRITING_TASK2_BAND_DESCRIPTORS.items():
        bands: dict[int, RubricCompatibilityStatus] = {}
        for raw_band in descriptors:
            band = int(raw_band)
            mapped = RUBRIC_KNOWLEDGE_MAP[criterion][band]
            if not all(identifier in snapshot_ids for identifier in mapped):
                raise ValueError("Rubric compatibility reference does not resolve")
            bands[band] = RubricCompatibilityStatus.COMPATIBLE_WITH_MISSING_PROVENANCE
        results[criterion] = MappingProxyType(bands)
    return MappingProxyType(results)
