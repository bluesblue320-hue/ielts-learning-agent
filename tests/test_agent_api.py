"""Phase 8 Agent public-route contract tests."""

from fastapi.routing import APIRoute

from app.main import create_app


def test_agent_turn_is_exposed_only_at_the_frozen_writing_path() -> None:
    routes = create_app().openapi()["paths"]
    assert "/learners/{learner_id}/writing/agent/turn" in routes
    assert "/learners/{learner_id}/agent/turn" not in routes
from fastapi.testclient import TestClient

from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_learning_api import _seed_evaluation, client, engine
from tests.test_practice_submission import _payload


def _agent_url(learner_id: int = 1) -> str:
    return f"/learners/{learner_id}/writing/agent/turn"


def test_agent_invalid_and_missing_learner_use_safe_api_contract(client: TestClient) -> None:
    invalid = client.post(_agent_url(), json={"turn_type": "invalid"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_invalid"
    missing = client.post(_agent_url(999), json={"turn_type": "continue"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "learner_not_found"


def test_agent_continue_returns_practice_ready_and_target_achieved(client: TestClient, engine) -> None:
    _seed_evaluation(engine)
    client.app.dependency_overrides[get_practice_generator] = lambda: FakePracticeGenerator()
    try:
        assert client.post("/learners/1/writing/evaluations/200/apply").status_code == 200
        ready = client.post(_agent_url(), json={"turn_type": "continue"})
        assert ready.status_code == 200
        assert ready.json()["stop_reason"] == "practice_ready"
        assert ready.json()["current_practice"] is not None
    finally:
        client.app.dependency_overrides.clear()


def test_agent_continue_target_achieved_is_provider_free(client: TestClient, engine) -> None:
    _seed_evaluation(engine, target="6.0", bands={skill: "6.5" for skill in ("task_response", "coherence_and_cohesion", "lexical_resource", "grammatical_range_and_accuracy")})
    assert client.post("/learners/1/writing/evaluations/200/apply").status_code == 200
    response = client.post(_agent_url(), json={"turn_type": "continue"})
    assert response.status_code == 200
    assert response.json()["stop_reason"] == "target_achieved"
    assert response.json()["steps"] == [{"tool": "observe", "outcome": "observation_classified"}]