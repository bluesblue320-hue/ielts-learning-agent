"""P10-07 offline Knowledge grounding evaluator coverage."""

from decimal import Decimal

from app.eval.knowledge import GroundingEvidence, evaluate_knowledge_grounding
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.common import BandScore
from app.schemas.knowledge import (
    GroundedCitation,
    GroundedRecommendationSummary,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
)
from app.schemas.writing import WritingCriterion


def _query() -> KnowledgeRetrievalQuery:
    return KnowledgeRetrievalQuery(
        purpose=KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
        criterion=WritingCriterion.TASK_RESPONSE,
        current_band=BandScore(value=Decimal("6.0")),
        target_band=BandScore(value=Decimal("6.5")),
        task_type="opinion",
    )


def _evidence(*, citation_owner: str = "application", target_skill: str = "task_response") -> GroundingEvidence:
    unit = WRITING_TASK2_KNOWLEDGE_UNITS[0]
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
        for reference in unit.source_refs
    )
    return GroundingEvidence(
        learner_id=11,
        current_learning_update_id=22,
        recommendation_learner_id=11,
        recommendation_learning_update_id=22,
        recommendation=GroundedRecommendationSummary(
            id=33,
            decision_type="practice",
            target_skill=target_skill,
            learner_target_band=BandScore(value=Decimal("6.5")),
            reason_codes=("largest_target_gap",),
        ),
        query=_query(),
        knowledge_ids=(unit.knowledge_id,),
        citations=citations,
        citation_owner=citation_owner,
    )


def test_known_snapshot_id_and_repeatable_retrieval_pass() -> None:
    finding = evaluate_knowledge_grounding(
        knowledge_ids=(WRITING_TASK2_KNOWLEDGE_UNITS[0].knowledge_id,),
        query=_query(),
    )

    assert finding.status.value == "pass"


def test_known_application_owned_citation_and_aligned_context_pass() -> None:
    evidence = _evidence()

    finding = evaluate_knowledge_grounding(
        knowledge_ids=evidence.knowledge_ids,
        evidence=evidence,
    )

    assert finding.status.value == "pass"


def test_unknown_knowledge_identity_fails_closed_as_veto() -> None:
    finding = evaluate_knowledge_grounding(knowledge_ids=("unknown-knowledge-id",))

    assert finding.severity.value == "veto"
    assert finding.failure_codes == ("knowledge_unknown_id",)


def test_unknown_source_locator_and_provider_invented_citation_fail_closed() -> None:
    evidence = _evidence()
    citation = evidence.citations[0].model_copy(update={"locator": "invented locator"})
    unknown_locator = evidence.model_copy(update={"citations": (citation,)})
    provider_owned = _evidence(citation_owner="provider")

    assert evaluate_knowledge_grounding(
        knowledge_ids=unknown_locator.knowledge_ids, evidence=unknown_locator
    ).failure_codes == ("knowledge_unknown_citation",)
    assert evaluate_knowledge_grounding(
        knowledge_ids=provider_owned.knowledge_ids, evidence=provider_owned
    ).failure_codes == ("knowledge_provider_invented_citation",)


def test_recommendation_context_mismatch_fails_closed() -> None:
    evidence = _evidence()
    mismatched = evidence.model_copy(update={"recommendation_learner_id": 99})

    finding = evaluate_knowledge_grounding(
        knowledge_ids=mismatched.knowledge_ids, evidence=mismatched
    )

    assert finding.failure_codes == ("knowledge_recommendation_context_mismatch",)