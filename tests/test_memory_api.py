"""P6-08 public read-contract API tests (isolated PostgreSQL).

Covers the four frozen read endpoints, safe error codes, the full resume
action matrix, older-unfinished-practice non-override, the unapplied initial
evaluation limitation, and zero provider calls for reads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import create_session_factory
from app.models.learning import Learner, PracticeRecommendation
from app.models.practice import WritingPractice
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_learning_api import _seed_learner, client, engine
from tests.test_memory_queries import _apply_initial, _complete_targeted_practice, _seed_full_evaluation
from tests.test_practice_submission import _payload

DT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _assert_safe_error(response, *, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["fields"] == []


def _generate_practice(client: TestClient, engine, learner_id: int = 1) -> int:
    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation is not None
        recommendation_id = recommendation.id
    generator = FakePracticeGenerator()
    client.app.dependency_overrides[get_practice_generator] = lambda: generator
    try:
        generated = client.post(
            f"/learners/{learner_id}/writing/recommendations/{recommendation_id}/practice"
        )
        assert generated.status_code == 200
        return generated.json()["practice"]["id"]
    finally:
        client.app.dependency_overrides.pop(get_practice_generator, None)
        client.app.dependency_overrides.pop(get_writing_provider, None)


def _submit_practice(client: TestClient, practice_id: int, learner_id: int = 1) -> None:
    provider = FakeProvider([_payload()])
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        submitted = client.post(
            f"/learners/{learner_id}/writing/practices/{practice_id}/submit",
            json={"essay": "A submitted practice essay with sufficient detail."},
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "submitted"
    finally:
        client.app.dependency_overrides.pop(get_practice_generator, None)
        client.app.dependency_overrides.pop(get_writing_provider, None)


def test_history_no_learner_404(client: TestClient, engine) -> None:
    _assert_safe_error(
        client.get("/learners/99/writing/history"),
        status_code=404,
        code="learner_not_found",
    )


def test_history_empty_learner(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    response = client.get("/learners/1/writing/history")
    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] == 1
    assert body["episodes"] == []


def test_history_initial_then_targeted_ordering(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    _complete_targeted_practice(client, engine)
    response = client.get("/learners/1/writing/history")
    assert response.status_code == 200
    episodes = response.json()["episodes"]
    assert [e["episode_type"] for e in episodes] == ["targeted_practice", "initial_writing"]
    assert episodes[0]["occurred_at"] >= episodes[1]["occurred_at"]
    assert episodes[0]["writing_practice_id"] is not None
    assert episodes[1]["writing_practice_id"] is None


def test_episode_detail_and_ownership(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    episode_id = _apply_initial(client, engine)
    detail = client.get(f"/learners/1/writing/history/{episode_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["episode"]["episode_id"] == episode_id
    assert body["attempt"]["question"] == "Q"
    assert len(body["evidence"]) == 4
    assert body["recommendation"]["decision_type"] == "practice"

    _seed_learner(engine, learner_id=2)
    _assert_safe_error(
        client.get(f"/learners/2/writing/history/{episode_id}"),
        status_code=404,
        code="episode_not_found",
    )
    _assert_safe_error(
        client.get("/learners/1/writing/history/9999"),
        status_code=404,
        code="episode_not_found",
    )


def test_progress_reads_l2_and_l3(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    response = client.get("/learners/1/writing/progress")
    assert response.status_code == 200
    body = response.json()
    assert body["current_writing_target_band"]["value"] == "7.0"
    assert body["memory_version"] == "writing-memory-v1"
    assert body["progress_version"] == "writing-progress-v1"
    tr = body["skills"]["task_response"]
    assert tr["trend"] == "insufficient_history"
    assert tr["persistent_gap_status"] == "insufficient_history"
    assert tr["current_estimate"] == "6.00"
    assert tr["source_observation_ids"] == [1]
    _assert_safe_error(
        client.get("/learners/99/writing/progress"),
        status_code=404,
        code="learner_not_found",
    )


def test_context_initial_writing_when_no_episodes(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    context = client.get("/learners/1/writing/context")
    assert context.status_code == 200
    body = context.json()
    assert body["resume_action"] == "initial_writing"
    assert body["has_learner_owned_episodes"] is False
    assert body["latest_learning_update_id"] is None


def test_context_generate_practice_after_apply(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    context = client.get("/learners/1/writing/context")
    body = context.json()
    assert body["resume_action"] == "generate_practice"
    assert body["current_recommendation"]["decision_type"] == "practice"
    assert body["relevant_practice"] is None


def test_context_submit_practice_after_generate(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    _generate_practice(client, engine)
    context = client.get("/learners/1/writing/context")
    assert context.json()["resume_action"] == "submit_practice"
    assert context.json()["relevant_practice"]["lifecycle_state"] == "generated"


def test_context_await_submission_when_claim_in_progress(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    practice_id = _generate_practice(client, engine)
    with create_session_factory(engine)() as session:
        practice = session.get(WritingPractice, practice_id)
        assert practice is not None
        practice.lifecycle_state = "submission_in_progress"
        practice.claim_token = "claim-token"
        session.commit()
    context = client.get("/learners/1/writing/context")
    assert context.json()["resume_action"] == "await_submission"


def test_context_complete_practice_after_submit(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    practice_id = _generate_practice(client, engine)
    _submit_practice(client, practice_id)
    context = client.get("/learners/1/writing/context")
    body = context.json()
    assert body["resume_action"] == "complete_practice"
    assert body["relevant_practice"]["lifecycle_state"] == "submitted"


def test_context_no_action_when_target_achieved(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _seed_full_evaluation(
        engine,
        evaluation_id=200,
        attempt_id=100,
        bands={
            "task_response": "7.0",
            "coherence_and_cohesion": "7.0",
            "lexical_resource": "7.0",
            "grammatical_range_and_accuracy": "7.0",
        },
    )
    applied = client.post("/learners/1/writing/evaluations/200/apply")
    assert applied.status_code == 200
    context = client.get("/learners/1/writing/context")
    body = context.json()
    assert body["resume_action"] == "no_action"
    assert body["current_recommendation"]["decision_type"] == "no_practice"


def test_context_after_complete_uses_new_latest_recommendation(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    result = _complete_targeted_practice(client, engine)
    context = client.get("/learners/1/writing/context")
    body = context.json()
    # The completed practice belongs to an OLDER recommendation; context must
    # reflect the NEW latest recommendation (a fresh practice decision).
    assert body["resume_action"] == "generate_practice"
    assert body["latest_learning_update_id"] == result["learning_update_id"]
    assert body["current_recommendation_id"] == result["next_recommendation_id"]
    assert body["relevant_practice"] is None


def test_older_unfinished_practice_does_not_override(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)  # episode 1 -> recommendation (practice)
    practice_id = _generate_practice(client, engine)  # practice remains generated
    # A newer initial evaluation is applied while the old practice is unfinished.
    _seed_full_evaluation(
        engine,
        evaluation_id=201,
        attempt_id=101,
        bands={
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
    )
    applied = client.post("/learners/1/writing/evaluations/201/apply")
    assert applied.status_code == 200
    context = client.get("/learners/1/writing/context")
    body = context.json()
    # The newer recommendation wins: its own (not-yet-generated) practice is
    # the relevant one. The older generated practice stays in history and is
    # NOT used as the resume point.
    assert body["resume_action"] == "generate_practice"
    assert body["relevant_practice"] is None
    with create_session_factory(engine)() as session:
        practice = session.get(WritingPractice, practice_id)
        assert practice is not None
        assert practice.lifecycle_state == "generated"
    history = client.get("/learners/1/writing/history").json()["episodes"]
    assert len(history) == 2


def test_unapplied_initial_evaluation_is_not_server_recoverable(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    provider = FakeProvider([_payload()])
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        evaluated = client.post(
            "/writing/evaluate",
            json={"question": "Q", "essay": "An evaluated but never applied essay."},
        )
        assert evaluated.status_code == 201
    finally:
        client.app.dependency_overrides.pop(get_practice_generator, None)
        client.app.dependency_overrides.pop(get_writing_provider, None)
    # The evaluation is persisted but NOT learner-owned: context falls back to
    # initial_writing and history is empty (resume v1 limitation).
    context = client.get("/learners/1/writing/context")
    assert context.json()["resume_action"] == "initial_writing"
    history = client.get("/learners/1/writing/history")
    assert history.json()["episodes"] == []


def test_reads_make_zero_provider_calls(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    provider = FakeProvider([])
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        assert client.get("/learners/1/writing/history").status_code == 200
        assert client.get("/learners/1/writing/progress").status_code == 200
        assert client.get("/learners/1/writing/context").status_code == 200
        episode_id = client.get("/learners/1/writing/history").json()["episodes"][0]["episode_id"]
        assert client.get(f"/learners/1/writing/history/{episode_id}").status_code == 200
    finally:
        client.app.dependency_overrides.pop(get_practice_generator, None)
        client.app.dependency_overrides.pop(get_writing_provider, None)
    assert provider.requests == []
