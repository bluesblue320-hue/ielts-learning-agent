from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import create_app


class _Session:
    def __init__(
        self,
        *,
        learner: object | None,
        update: object | None = None,
        recommendation: object | None = None,
    ) -> None:
        self.learner = learner
        self.update = update
        self.recommendation = recommendation
        self.scalar_calls = 0

    def get(self, _model: object, _identifier: int) -> object | None:
        return self.learner

    def scalar(self, _query: object) -> object | None:
        self.scalar_calls += 1
        return self.update if self.scalar_calls == 1 else self.recommendation

    def rollback(self) -> None:
        pass


def _client(session: _Session) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: session
    return TestClient(application)


def _learner() -> object:
    return SimpleNamespace(id=1, writing_target_band=Decimal("7.0"))


def _snapshot() -> dict[str, object]:
    return {
        skill: {
            "learner_id": 1,
            "skill": skill,
            "estimated_band": "6.25" if skill == "task_response" else "7.00",
            "evidence_count": 3,
            "last_evidence_id": index,
            "state_policy_version": "writing-state-ewma-v1",
            "revision": 3,
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        for index, skill in enumerate(
            (
                "task_response",
                "coherence_and_cohesion",
                "lexical_resource",
                "grammatical_range_and_accuracy",
            ),
            start=1,
        )
    }


def _recommendation() -> object:
    return SimpleNamespace(
        id=10,
        decision_type="practice",
        target_skill="task_response",
        learner_target_band=Decimal("7.0"),
        current_estimate=Decimal("6.25"),
        reason_codes=["largest_target_gap"],
        planner_version="writing-practice-gap-v1",
        state_snapshot=_snapshot(),
        planner_context_snapshot=None,
    )


def test_guidance_route_is_exactly_one_read_only_public_surface() -> None:
    application = create_app()
    paths = application.openapi()["paths"]
    guidance = paths["/learners/{learner_id}/writing/guidance"]
    assert set(guidance) == {"get"}
    assert all("/knowledge/search" not in path for path in paths)


def test_guidance_api_returns_safe_empty_state_before_first_update() -> None:
    response = _client(_Session(learner=_learner())).get("/learners/1/writing/guidance")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "learner_state",
        "current_recommendation",
        "guidance_items",
        "source_citations",
        "guidance_version",
        "knowledge_version",
        "retrieval_version",
    }
    assert body["current_recommendation"] is None
    assert body["guidance_items"] == []
    assert body["source_citations"] == []
    assert body["guidance_version"] == "writing-grounded-guidance-v1"


def test_guidance_api_returns_grounded_practice_guidance_without_provider() -> None:
    session = _Session(
        learner=_learner(),
        update=SimpleNamespace(id=9),
        recommendation=_recommendation(),
    )
    response = _client(session).get("/learners/1/writing/guidance")
    assert response.status_code == 200
    body = response.json()
    assert body["current_recommendation"]["target_skill"] == "task_response"
    assert body["learner_state"]["current_estimates"]["task_response"] == "6.25"
    assert body["guidance_items"][0]["knowledge_ids"]
    assert body["source_citations"][0]["url"].startswith("https://ielts.org/")


def test_guidance_api_uses_existing_safe_learner_not_found_error() -> None:
    response = _client(_Session(learner=None)).get("/learners/99/writing/guidance")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "learner_not_found"
