from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.common import BandScore
from app.schemas.knowledge import (
    KNOWLEDGE_VERSION,
    KnowledgeCategory,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
    KnowledgeSourceRef,
    KnowledgeUnit,
)


def _unit(**overrides: object) -> KnowledgeUnit:
    values: dict[str, object] = {
        "knowledge_id": "writing-tr-band-7",
        "category": KnowledgeCategory.BAND_GUIDANCE,
        "criterion": "task_response",
        "descriptor_band": 7,
        "statement": "A clear position and developed relevant ideas are expected.",
        "source_refs": (
            KnowledgeSourceRef(
                source_id="ielts-writing-band-descriptors-2023",
                locator="Writing Task 2 / Task Response / Band 7",
                section="Task Response",
            ),
        ),
    }
    values.update(overrides)
    return KnowledgeUnit.model_validate(values)


def test_knowledge_unit_is_strict_immutable_and_integer_band_only() -> None:
    unit = _unit()
    assert unit.knowledge_version == KNOWLEDGE_VERSION
    with pytest.raises(ValidationError):
        _unit(unexpected="no")
    with pytest.raises(ValidationError):
        _unit(descriptor_band=6.5)
    with pytest.raises(ValidationError):
        _unit(knowledge_id="Not stable")
    with pytest.raises(ValidationError):
        unit.descriptor_band = 6


def test_knowledge_unit_cannot_hold_learner_specific_fields_or_purpose() -> None:
    with pytest.raises(ValidationError):
        _unit(learner_id=1)
    with pytest.raises(ValidationError):
        _unit(purpose="learner_guidance")


def test_source_reference_requires_stable_source_and_claim_locator() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSourceRef(source_id="source", locator=" ")
    with pytest.raises(ValidationError):
        KnowledgeSourceRef(source_id="Invalid Source", locator="section")


def test_retrieval_query_owns_closed_purpose_and_validates_bands() -> None:
    query = KnowledgeRetrievalQuery(
        purpose=KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
        criterion="task_response",
        current_band=BandScore(value=Decimal("6.5")),
        target_band=BandScore(value=Decimal("7.0")),
    )
    assert query.purpose is KnowledgeRetrievalPurpose.LEARNER_GUIDANCE
    with pytest.raises(ValidationError):
        KnowledgeRetrievalQuery(purpose="semantic_search", criterion="task_response", target_band={"value": "7.0"})
    with pytest.raises(ValidationError):
        KnowledgeRetrievalQuery(purpose="learner_guidance", criterion="task_response", target_band={"value": "6.3"})
    with pytest.raises(ValidationError):
        KnowledgeRetrievalQuery(purpose="learner_guidance", target_band={"value": "7.0"})


def test_serialization_is_deterministic() -> None:
    assert _unit().model_dump_json() == _unit().model_dump_json()
