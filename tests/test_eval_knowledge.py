"""P10-07 offline Knowledge grounding evaluator coverage."""

from decimal import Decimal

from app.eval.knowledge import GroundingEvidence, evaluate_knowledge_grounding
from app.knowledge.retriever import retrieve_knowledge
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.common import BandScore
from app.schemas.knowledge import (
    GroundedCitation,
    GroundedRecommendationSummary,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
)


def _query(
    purpose: KnowledgeRetrievalPurpose = KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
    *,
    criterion: str = "task_response",
    current_band: str = "6.0",
    target_band: str = "6.5",
) -> KnowledgeRetrievalQuery:
    return KnowledgeRetrievalQuery(
        purpose=purpose,
        criterion=criterion,
        current_band=BandScore(value=Decimal(current_band)),
        target_band=BandScore(value=Decimal(target_band)),
    )


def _evidence(
    *,
    purpose: KnowledgeRetrievalPurpose = KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
    citation_owner: str = "application",
    target_skill: str = "task_response",
    query_criterion: str | None = None,
    target_band: str = "6.5",
    query_target_band: str | None = None,
    current_estimate: Decimal | None = Decimal("6.0"),
    query_current_band: str = "6.0",
    learner_id: int = 11,
    update_id: int = 22,
) -> GroundingEvidence:
    query = _query(
        purpose,
        criterion=query_criterion or target_skill,
        current_band=query_current_band,
        target_band=query_target_band or target_band,
    )
    units = retrieve_knowledge(query).units
    citations = tuple(
        GroundedCitation(
            source_id=reference.source_id,
            publisher=KNOWLEDGE_SOURCES[reference.source_id].publisher,
            title=KNOWLEDGE_SOURCES[reference.source_id].title,
            url=KNOWLEDGE_SOURCES[reference.source_id].url,
            locator=reference.locator,
            page=reference.page,
            section=reference.section,
        )
        for unit in units
        for reference in unit.source_refs
    )
    return GroundingEvidence(
        learner_id=learner_id,
        current_learning_update_id=update_id,
        recommendation_learner_id=learner_id,
        recommendation_learning_update_id=update_id,
        recommendation=GroundedRecommendationSummary(
            id=33,
            decision_type="practice",
            target_skill=target_skill,
            learner_target_band=BandScore(value=Decimal(target_band)),
            current_estimate=current_estimate,
            reason_codes=("largest_target_gap",),
        ),
        query=query,
        knowledge_ids=tuple(unit.knowledge_id for unit in units),
        citations=(
            citations
            if purpose is KnowledgeRetrievalPurpose.LEARNER_GUIDANCE
            else ()
        ),
        practice_knowledge_source_ids=(
            {}
            if purpose is KnowledgeRetrievalPurpose.LEARNER_GUIDANCE
            else {
                unit.knowledge_id: tuple(
                    reference.source_id for reference in unit.source_refs
                )
                for unit in units
            }
        ),
        citation_owner=citation_owner,
    )


def test_known_snapshot_id_and_repeatable_retrieval_pass() -> None:
    query = _query()
    knowledge_ids = tuple(
        unit.knowledge_id for unit in retrieve_knowledge(query).units
    )
    finding = evaluate_knowledge_grounding(
        knowledge_ids=knowledge_ids,
        query=query,
    )
    assert finding.status.value == "pass"


def test_aligned_guidance_and_practice_generation_grounding_pass() -> None:
    for purpose in (
        KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
        KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
    ):
        evidence = _evidence(purpose=purpose)
        assert evaluate_knowledge_grounding(
            knowledge_ids=evidence.knowledge_ids,
            evidence=evidence,
        ).status.value == "pass"


def test_generation_current_estimate_uses_production_half_up_normalization() -> None:
    for current_estimate, current_band in (
        (Decimal("6.24"), "6.0"),
        (Decimal("6.25"), "6.5"),
    ):
        evidence = _evidence(
            purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
            current_estimate=current_estimate,
            query_current_band=current_band,
        )
        assert evaluate_knowledge_grounding(
            knowledge_ids=evidence.knowledge_ids,
            evidence=evidence,
        ).status.value == "pass"


def test_generation_wrong_or_missing_current_band_authority_fails_closed() -> None:
    wrong_band = _evidence(
        purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
        current_estimate=Decimal("6.24"),
        query_current_band="6.5",
    )
    missing_estimate = _evidence(
        purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
        current_estimate=None,
    )
    for evidence in (wrong_band, missing_estimate):
        finding = evaluate_knowledge_grounding(
            knowledge_ids=evidence.knowledge_ids,
            evidence=evidence,
        )
        assert finding.severity.value == "veto"
        assert finding.failure_codes == (
            "knowledge_recommendation_context_mismatch",
        )


def test_unknown_and_out_of_scope_knowledge_fail_closed() -> None:
    query = _query()
    expected_ids = tuple(
        unit.knowledge_id for unit in retrieve_knowledge(query).units
    )
    out_of_scope = next(
        unit.knowledge_id
        for unit in WRITING_TASK2_KNOWLEDGE_UNITS
        if unit.knowledge_id not in expected_ids
    )
    assert evaluate_knowledge_grounding(
        knowledge_ids=("unknown-knowledge-id",),
    ).failure_codes == ("knowledge_unknown_id",)
    evidence = _evidence(
        purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
    )
    out_of_scope_unit = next(
        unit
        for unit in WRITING_TASK2_KNOWLEDGE_UNITS
        if unit.knowledge_id == out_of_scope
    )
    poisoned = evidence.model_copy(
        update={
            "knowledge_ids": evidence.knowledge_ids + (out_of_scope,),
            "practice_knowledge_source_ids": {
                **evidence.practice_knowledge_source_ids,
                out_of_scope: tuple(
                    reference.source_id
                    for reference in out_of_scope_unit.source_refs
                ),
            },
        }
    )
    finding = evaluate_knowledge_grounding(
        knowledge_ids=poisoned.knowledge_ids,
        evidence=poisoned,
    )
    assert finding.severity.value == "major"
    assert finding.failure_codes == ("knowledge_practice_scope_mismatch",)


def test_unknown_locator_and_provider_citation_fail_closed() -> None:
    guidance = _evidence()
    bad_citation = guidance.citations[0].model_copy(
        update={"locator": "invented locator"}
    )
    assert evaluate_knowledge_grounding(
        knowledge_ids=guidance.knowledge_ids,
        evidence=guidance.model_copy(update={"citations": (bad_citation,)}),
    ).failure_codes == ("knowledge_unknown_citation",)
    assert evaluate_knowledge_grounding(
        knowledge_ids=guidance.knowledge_ids,
        evidence=_evidence(citation_owner="provider"),
    ).failure_codes == ("knowledge_provider_invented_citation",)


def test_generation_target_and_ownership_mismatches_fail_closed() -> None:
    wrong_skill = _evidence(
        purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
        query_criterion="lexical_resource",
    )
    wrong_target_band = _evidence(
        purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
        query_target_band="7.0",
    )
    wrong_owner = _evidence(
        purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
        learner_id=99,
    ).model_copy(update={"recommendation_learner_id": 11})
    for evidence in (wrong_skill, wrong_target_band, wrong_owner):
        finding = evaluate_knowledge_grounding(
            knowledge_ids=evidence.knowledge_ids,
            evidence=evidence,
        )
        assert finding.severity.value == "veto"
        assert finding.failure_codes == (
            "knowledge_recommendation_context_mismatch",
        )


def test_generation_unknown_source_mapping_fails_closed() -> None:
    evidence = _evidence(
        purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
    )
    poisoned = evidence.model_copy(
        update={
            "practice_knowledge_source_ids": {
                evidence.knowledge_ids[0]: ("invented-source",),
            }
        }
    )
    assert evaluate_knowledge_grounding(
        knowledge_ids=poisoned.knowledge_ids,
        evidence=poisoned,
    ).failure_codes == ("knowledge_generation_source_mismatch",)