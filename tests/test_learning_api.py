"""P3-11 learner and learning API integration tests against isolated PostgreSQL."""

import os
from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.db.session import create_session_factory, get_db_session
from app.main import create_app
from app.models.learning import Learner
from app.models.writing import WritingAttempt, WritingEvaluation

DT = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture
def engine(database_url: str) -> Generator[Engine, None, None]:
    command.upgrade(_alembic_config(database_url), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE practice_recommendations, learner_skill_states, "
                "learning_evidence, learning_updates, learners, "
                "writing_evaluations, writing_attempts RESTART IDENTITY CASCADE"
            )
        )
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE practice_recommendations, learner_skill_states, "
                    "learning_evidence, learning_updates, learners, "
                    "writing_evaluations, writing_attempts RESTART IDENTITY CASCADE"
                )
            )
        engine.dispose()


@pytest.fixture
def client(engine: Engine) -> Generator[TestClient, None, None]:
    session_factory = create_session_factory(engine)

    def session_override():
        with session_factory() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_db_session] = session_override
    with TestClient(application) as test_client:
        yield test_client


def _seed_learner(engine: Engine, learner_id: int = 1, target: str = "7.0") -> None:
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(Learner(id=learner_id, writing_target_band=Decimal(target)))
        session.commit()


def _seed_evaluation(
    engine: Engine,
    *,
    evaluation_id: int = 200,
    attempt_id: int = 100,
    target: str = "7.0",
    bands: dict[str, str] | None = None,
    created_at: datetime = DT,
) -> None:
    if bands is None:
        bands = {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(Learner(id=1, writing_target_band=Decimal(target)))
        session.add(
            WritingAttempt(
                id=attempt_id,
                question="Q",
                essay="E",
                word_count=1,
                created_at=created_at,
            )
        )
        session.add(
            WritingEvaluation(
                id=evaluation_id,
                attempt_id=attempt_id,
                task_response_band=Decimal(bands["task_response"]),
                coherence_and_cohesion_band=Decimal(bands["coherence_and_cohesion"]),
                lexical_resource_band=Decimal(bands["lexical_resource"]),
                grammatical_range_and_accuracy_band=Decimal(
                    bands["grammatical_range_and_accuracy"]
                ),
                product_band=Decimal("6.5"),
                criteria_feedback={},
                strengths=[],
                weaknesses=[],
                error_tags=[],
                recommended_skills=[],
                feedback="f",
                provider="deepseek",
                model="m",
                prompt_version="pv",
                rubric_version="rv",
                scoring_policy_version="sv",
                thinking_mode="disabled",
                created_at=created_at,
            )
        )
        session.commit()


# ---------------------------------------------------------------------------
# Learner creation
# ---------------------------------------------------------------------------


def test_create_learner_valid(client: TestClient) -> None:
    response = client.post(
        "/learners", json={"writing_target_band": {"value": "7.0"}}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["writing_target_band"]["value"] == "7.0"
    assert "created_at" in body and "updated_at" in body


def test_create_learner_invalid_target(client: TestClient) -> None:
    response = client.post(
        "/learners", json={"writing_target_band": {"value": "5.3"}}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_invalid"


# ---------------------------------------------------------------------------
# State inspection
# ---------------------------------------------------------------------------


def test_state_before_evidence_is_unobserved(client: TestClient, engine: Engine) -> None:
    _seed_learner(engine)
    response = client.get("/learners/1/state")
    assert response.status_code == 200
    states = response.json()["states"]
    assert set(states) == {
        "task_response",
        "coherence_and_cohesion",
        "lexical_resource",
        "grammatical_range_and_accuracy",
    }
    for skill_state in states.values():
        assert skill_state["estimated_band"] is None
        assert skill_state["evidence_count"] == 0
        assert skill_state["revision"] == 0


def test_state_after_evidence_is_observed(client: TestClient, engine: Engine) -> None:
    _seed_evaluation(engine)
    response = client.post("/learners/1/writing/evaluations/200/apply")
    assert response.status_code == 200
    response = client.get("/learners/1/state")
    states = response.json()["states"]
    assert states["task_response"]["estimated_band"] == "6.00"
    assert states["task_response"]["evidence_count"] == 1
    assert states["task_response"]["revision"] == 1
    assert states["coherence_and_cohesion"]["estimated_band"] == "6.50"


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def test_apply_practice_decision(client: TestClient, engine: Engine) -> None:
    _seed_evaluation(engine)
    response = client.post("/learners/1/writing/evaluations/200/apply")
    assert response.status_code == 200
    body = response.json()
    assert body["reused"] is False
    assert body["learning_update_id"] > 0
    recommendation = body["recommendation"]
    assert recommendation["decision_type"] == "practice"
    assert recommendation["target_skill"] == "task_response"
    assert recommendation["reason_codes"] == ["largest_target_gap", "insufficient_evidence"]
    assert recommendation["planner_version"] == "writing-practice-gap-v1"
    assert recommendation["current_estimate"] == "6.00"
    assert set(recommendation["state_snapshot"]) == {
        "task_response",
        "coherence_and_cohesion",
        "lexical_resource",
        "grammatical_range_and_accuracy",
    }


def test_apply_no_practice_decision(client: TestClient, engine: Engine) -> None:
    _seed_evaluation(
        engine,
        target="6.0",
        bands={
            "task_response": "6.5",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
    )
    response = client.post("/learners/1/writing/evaluations/200/apply")
    assert response.status_code == 200
    recommendation = response.json()["recommendation"]
    assert recommendation["decision_type"] == "no_practice"
    assert recommendation["target_skill"] is None
    assert recommendation["reason_codes"][0] == "target_achieved"


def test_idempotent_replay_via_api(client: TestClient, engine: Engine) -> None:
    _seed_evaluation(engine)
    first = client.post("/learners/1/writing/evaluations/200/apply")
    second = client.post("/learners/1/writing/evaluations/200/apply")
    assert second.status_code == 200
    assert second.json()["reused"] is True
    assert second.json()["learning_update_id"] == first.json()["learning_update_id"]
    assert (
        second.json()["recommendation"]
        == first.json()["recommendation"]
    )


def test_cross_owner_conflict_via_api(client: TestClient, engine: Engine) -> None:
    _seed_evaluation(engine)
    client.post("/learners/1/writing/evaluations/200/apply")
    _seed_learner(engine, learner_id=2)
    response = client.post("/learners/2/writing/evaluations/200/apply")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "evaluation_conflict"


def test_learner_not_found_via_api(client: TestClient) -> None:
    response = client.post("/learners/999/writing/evaluations/200/apply")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "learner_not_found"


def test_evaluation_not_found_via_api(client: TestClient, engine: Engine) -> None:
    _seed_learner(engine)
    response = client.post("/learners/1/writing/evaluations/999/apply")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "evaluation_not_found"


def test_state_not_found_via_api(client: TestClient) -> None:
    response = client.get("/learners/999/state")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "learner_not_found"


def test_error_responses_do_not_leak_internals(client: TestClient) -> None:
    response = client.post("/learners/999/writing/evaluations/200/apply")
    assert response.status_code == 404
    body = response.json()
    # Safe, stable error contract only: no exception text, no traceback,
    # no internal class names or essay content.
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "fields"}
    assert body["error"]["message"]
    assert body["error"]["fields"] == []
    assert "NotFoundError" not in body["error"]["message"]
    assert "Traceback" not in str(body)
