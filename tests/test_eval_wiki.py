"""Phase 11 deterministic Wiki extension of the Phase 10 Eval harness."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.eval.wiki import WikiEvalEvidence, evaluate_wiki_knowledge
from app.eval.schemas import EvalSeverity, EvalStatus
from app.main import create_app
from app.schemas.common import BandScore
from app.schemas.knowledge import KnowledgeRetrievalPurpose, KnowledgeRetrievalQuery
from app.schemas.wiki import WikiNeighborDirection, WikiRelationType
from app.wiki.relations import WIKI_RELATIONS
from app.wiki.service import WIKI_SERVICE


def _evidence(**updates: object) -> WikiEvalEvidence:
    values: dict[str, object] = {
        "guidance_knowledge_ids": (
            "writing-task-response-band-6",
            "writing-task-response-band-7",
            "writing-task-response-criterion",
            "writing-task2-minimum-250-words",
            "writing-task2-connected-text",
            "writing-task2-answer-prompt-directly",
        ),
        "guidance_page_ids": (
            "writing-task2-task-response-band-6",
            "writing-task2-task-response-band-7",
            "writing-task2-task-response",
            "writing-task2-rule-minimum-250-words",
            "writing-task2-rule-connected-text",
            "writing-task2-rule-answer-prompt-directly",
        ),
        "guidance_query": KnowledgeRetrievalQuery(
            purpose=KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
            criterion="task_response",
            current_band=BandScore(value=Decimal("6.0")),
            target_band=BandScore(value=Decimal("6.5")),
        ),
        "expected_retrieval_ids": (
            "writing-task-response-band-6",
            "writing-task-response-band-7",
            "writing-task-response-criterion",
            "writing-task2-minimum-250-words",
            "writing-task2-connected-text",
            "writing-task2-answer-prompt-directly",
        ),
    }
    values.update(updates)
    return WikiEvalEvidence.model_validate(values)


def test_canonical_wiki_evidence_passes_complete_deterministic_eval() -> None:
    finding = evaluate_wiki_knowledge(_evidence())
    assert finding.status.value == "pass"
    assert finding.evaluator.value == "wiki_knowledge"


def test_wiki_eval_vetoes_unknown_mapping_and_authority_changes() -> None:
    unknown = _evidence(
        guidance_knowledge_ids=("unknown-knowledge-id",),
        guidance_page_ids=("writing-task2",),
    )
    assert evaluate_wiki_knowledge(unknown).failure_codes == (
        "wiki_guidance_unknown_knowledge",
    )
    assert evaluate_wiki_knowledge(
        _evidence(identity_owner="provider")
    ).failure_codes == ("wiki_provider_identity_authority",)
    assert evaluate_wiki_knowledge(
        _evidence(planner_authority_preserved=False)
    ).failure_codes == ("wiki_authority_boundary_changed",)


def test_wiki_eval_vetoes_relation_or_retrieval_corruption() -> None:
    relation = WIKI_RELATIONS[0].model_copy(update={"relation_type": "related_to"})
    corrupted = (relation,) + WIKI_RELATIONS[1:]
    assert evaluate_wiki_knowledge(
        _evidence(), relations=corrupted
    ).failure_codes == ("wiki_snapshot_integrity",)
    assert evaluate_wiki_knowledge(
        _evidence(expected_retrieval_ids=("writing-task-response-band-7",))
    ).failure_codes == ("wiki_changed_adaptive_retrieval",)


def test_wiki_eval_vetoes_stable_wrong_neighbor_projection(monkeypatch) -> None:
    original_neighbors = WIKI_SERVICE.neighbors

    def stable_wrong_neighbors(page):
        neighbors = original_neighbors(page)
        if page.page_id != "writing-task2-task-response-band-7":
            return neighbors
        return (
            neighbors[0],
            neighbors[1].model_copy(
                update={"direction": WikiNeighborDirection.NEXT_BAND}
            ),
            neighbors[2],
        )

    monkeypatch.setattr(WIKI_SERVICE, "neighbors", stable_wrong_neighbors)

    finding = evaluate_wiki_knowledge(_evidence())

    assert finding.status is EvalStatus.FAIL
    assert finding.severity is EvalSeverity.VETO
    assert finding.failure_codes == ("wiki_neighbor_projection_mismatch",)


def test_wiki_api_is_read_only_and_preserves_safe_failures() -> None:
    application = create_app()
    paths = application.openapi()["paths"]
    assert set(paths["/knowledge/writing/wiki"]) == {"get"}
    assert set(paths["/knowledge/writing/wiki/{page_id}"]) == {"get"}
    client = TestClient(application)
    malformed = client.get("/knowledge/writing/wiki/writing--task2")
    unknown = client.get("/knowledge/writing/wiki/writing-task2-unknown")
    assert (malformed.status_code, malformed.json()["error"]["code"]) == (
        422,
        "request_invalid",
    )
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (
        404,
        "wiki_page_not_found",
    )


def test_wiki_relation_inventory_remains_frozen() -> None:
    assert len(WIKI_RELATIONS) == 93
    assert sum(
        relation.relation_type is WikiRelationType.CONTAINS
        for relation in WIKI_RELATIONS
    ) == 57
    assert sum(
        relation.relation_type is WikiRelationType.ADJACENT_BAND
        for relation in WIKI_RELATIONS
    ) == 36
