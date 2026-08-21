from decimal import Decimal

from app.knowledge.retriever import MAX_RESULTS_BY_PURPOSE, descriptor_bands, retrieve_knowledge
from app.schemas.common import BandScore
from app.schemas.knowledge import KnowledgeRetrievalPurpose, KnowledgeRetrievalQuery


def _query(purpose: KnowledgeRetrievalPurpose, current: str = "6.5", target: str = "7.0") -> KnowledgeRetrievalQuery:
    return KnowledgeRetrievalQuery(
        purpose=purpose,
        criterion="task_response",
        current_band=BandScore(value=Decimal(current)),
        target_band=BandScore(value=Decimal(target)),
        task_type="opinion",
    )


def test_half_band_mapping_is_integer_only_and_caps_at_nine() -> None:
    assert descriptor_bands(Decimal("6.0")) == (6,)
    assert descriptor_bands(Decimal("6.5")) == (6, 7)
    assert descriptor_bands(Decimal("7.5")) == (7, 8)
    assert descriptor_bands(Decimal("9.0")) == (9,)


def test_retrieval_is_deterministic_bounded_and_deduplicated() -> None:
    result = retrieve_knowledge(_query(KnowledgeRetrievalPurpose.LEARNER_GUIDANCE, "6.5", "7.0"))
    repeat = retrieve_knowledge(_query(KnowledgeRetrievalPurpose.LEARNER_GUIDANCE, "6.5", "7.0"))
    assert [unit.knowledge_id for unit in result.units] == [unit.knowledge_id for unit in repeat.units]
    assert len(result.units) <= MAX_RESULTS_BY_PURPOSE[KnowledgeRetrievalPurpose.LEARNER_GUIDANCE]
    assert len({unit.knowledge_id for unit in result.units}) == len(result.units)
    assert {unit.descriptor_band for unit in result.units if unit.descriptor_band is not None} >= {6, 7}


def test_purpose_selects_strategy_not_knowledge_metadata() -> None:
    practice = retrieve_knowledge(_query(KnowledgeRetrievalPurpose.PRACTICE_GENERATION))
    audit = retrieve_knowledge(_query(KnowledgeRetrievalPurpose.RUBRIC_COMPATIBILITY, "7.0"))
    assert all(unit.descriptor_band == 7 for unit in audit.units)
    assert any(unit.category.value == "task_rule" for unit in practice.units)
    assert all(not hasattr(unit, "purpose") for unit in practice.units)
