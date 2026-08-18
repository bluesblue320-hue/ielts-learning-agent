"""P4-12 API lifecycle coverage with deterministic provider fakes."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import create_session_factory
from app.models.learning import PracticeRecommendation
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_learning_api import _seed_evaluation, client, engine
from tests.test_practice_submission import _payload


def test_distinct_practice_lifecycle_actions(client: TestClient, engine) -> None:
    _seed_evaluation(engine)
    applied = client.post("/learners/1/writing/evaluations/200/apply")
    assert applied.status_code == 200
    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation is not None

    generator = FakePracticeGenerator()
    provider = FakeProvider([_payload()])
    client.app.dependency_overrides[get_practice_generator] = lambda: generator
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        generated = client.post(
            f"/learners/1/writing/recommendations/{recommendation.id}/practice"
        )
        assert generated.status_code == 200
        practice = generated.json()["practice"]
        assert practice is not None
        practice_id = practice["id"]

        inspected = client.get(f"/learners/1/writing/practices/{practice_id}")
        assert inspected.status_code == 200
        assert inspected.json()["question"] == practice["question"]

        submitted = client.post(
            f"/learners/1/writing/practices/{practice_id}/submit",
            json={"essay": "An essay supplied without a client question."},
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "submitted"
        assert len(provider.requests) == 1

        completed = client.post(
            f"/learners/1/writing/practices/{practice_id}/complete"
        )
        assert completed.status_code == 200
        assert "next_recommendation" in completed.json()
    finally:
        client.app.dependency_overrides.clear()
