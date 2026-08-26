"""P10-07 offline Knowledge grounding evaluator coverage."""

from decimal import Decimal

from app.eval.knowledge import evaluate_knowledge_grounding
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.common import BandScore
from app.schemas.knowledge import KnowledgeRetrievalPurpose, KnowledgeRetrievalQuery
from app.schemas.writing import WritingCriterion


def _query() -> KnowledgeRetrievalQuery:
    return KnowledgeRetrievalQuery(
        purpose=KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
        criterion=WritingCriterion.TASK_RESPONSE,
        current_band=BandScore(value=Decimal("6.0")),
        target_band=BandScore(value=Decimal("6.5")),
        task_type="opinion",
    )


def test_known_snapshot_id_and_repeatable_retrieval_pass() -> None:
    finding = evaluate_knowledge_grounding(
        knowledge_ids=(WRITING_TASK2_KNOWLEDGE_UNITS[0].knowledge_id,),
        query=_query(),
    )

    assert finding.status.value == "pass"


def test_unknown_knowledge_identity_fails_closed_as_veto() -> None:
    finding = evaluate_knowledge_grounding(knowledge_ids=("unknown-knowledge-id",))

    assert finding.severity.value == "veto"
    assert finding.failure_codes == ("knowledge_unknown_id",)
