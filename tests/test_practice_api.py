"""P4-12 public lifecycle and safe-failure contract coverage."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import create_session_factory
from app.models.learning import LearningUpdate, PracticeRecommendation
from app.models.practice import WritingPractice
from app.services.practice_completion import (
    PracticeCompletionPersistenceError,
    PracticeCompletionService,
)
from app.services.practice_generation import (
    GeneratedPracticeAuthorityError,
    PracticeGenerationPersistenceError,
    PracticeGenerationService,
)
from app.services.practice_submission import (
    PracticeSubmissionPersistenceError,
    PracticeSubmissionService,
)
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_learning_api import _seed_evaluation, _seed_learner, client, engine
from tests.test_practice_submission import _payload


def _practice_recommendation_id(client: TestClient, engine) -> int:
    _seed_evaluation(engine)
    applied = client.post("/learners/1/writing/evaluations/200/apply")
    assert applied.status_code == 200
    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation is not None
        return recommendation.id


def _generate(client: TestClient, recommendation_id: int) -> tuple[int, FakePracticeGenerator]:
    generator = FakePracticeGenerator()
    client.app.dependency_overrides[get_practice_generator] = lambda: generator
    response = client.post(f"/learners/1/writing/recommendations/{recommendation_id}/practice")
    assert response.status_code == 200
    practice = response.json()["practice"]
    assert practice is not None
    return practice["id"], generator


def _assert_safe_error(response, *, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "fields"}
    assert body["error"]["code"] == code
    assert body["error"]["fields"] == []
    for forbidden in (
        "SQLAlchemyError", "OperationalError", "Traceback", "claim_token",
        "fingerprint", "essay", "question", "provider internals", "boom",
    ):
        assert forbidden not in str(body)


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


def test_generation_decisions_idempotency_and_ownership_at_api_boundary(
    client: TestClient, engine
) -> None:
    recommendation_id = _practice_recommendation_id(client, engine)
    practice_id, generator = _generate(client, recommendation_id)
    try:
        retry = client.post(f"/learners/1/writing/recommendations/{recommendation_id}/practice")
        assert retry.status_code == 200
        assert retry.json()["practice"]["id"] == practice_id
        assert len(generator.requests) == 1

        _seed_learner(engine, learner_id=2)
        cross_owner = client.post(f"/learners/2/writing/recommendations/{recommendation_id}/practice")
        _assert_safe_error(cross_owner, status_code=409, code="practice_conflict")
        assert len(generator.requests) == 1
    finally:
        client.app.dependency_overrides.clear()


def test_no_practice_and_cold_start_generation_are_api_noops(client: TestClient, engine) -> None:
    _seed_evaluation(engine, target="6.0")
    applied = client.post("/learners/1/writing/evaluations/200/apply")
    assert applied.status_code == 200
    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation is not None
        no_practice_id = recommendation.id
    generator = FakePracticeGenerator()
    client.app.dependency_overrides[get_practice_generator] = lambda: generator
    try:
        response = client.post(f"/learners/1/writing/recommendations/{no_practice_id}/practice")
        assert response.status_code == 200
        assert response.json()["decision"] == "no_practice"
        assert not generator.requests
        with create_session_factory(engine)() as session:
            assert session.scalar(select(func.count()).select_from(WritingPractice)) == 0
    finally:
        client.app.dependency_overrides.clear()


def test_cold_start_generation_is_an_api_noop(client: TestClient, engine) -> None:
    _seed_evaluation(engine)
    with create_session_factory(engine)() as session:
        update = LearningUpdate(
            learner_id=1,
            writing_evaluation_id=200,
            skill_taxonomy_version="writing-core-v1",
            state_policy_version="writing-state-ewma-v1",
            planner_version="writing-practice-gap-v1",
        )
        session.add(update)
        session.flush()
        cold_start = PracticeRecommendation(
            learning_update_id=update.id,
            learner_id=1,
            decision_type="no_practice",
            target_skill=None,
            learner_target_band="7.0",
            current_estimate=None,
            reason_codes=["cold_start"],
            planner_version="writing-practice-gap-v1",
            state_snapshot={skill: {} for skill in (
                "task_response", "coherence_and_cohesion", "lexical_resource",
                "grammatical_range_and_accuracy",
            )},
        )
        session.add(cold_start)
        session.commit()
        cold_start_id = cold_start.id
    generator = FakePracticeGenerator()
    client.app.dependency_overrides[get_practice_generator] = lambda: generator
    try:
        cold = client.post(f"/learners/1/writing/recommendations/{cold_start_id}/practice")
        assert cold.status_code == 200
        assert cold.json()["decision"] == "no_practice"
        assert cold.json()["no_practice_reasons"] == ["cold_start"]
        assert not generator.requests
        with create_session_factory(engine)() as session:
            assert session.scalar(select(func.count()).select_from(WritingPractice)) == 0
    finally:
        client.app.dependency_overrides.clear()


def test_submission_and_inspection_public_contract(client: TestClient, engine) -> None:
    practice_id, _ = _generate(client, _practice_recommendation_id(client, engine))
    provider = FakeProvider([_payload()])
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        inspected = client.get(f"/learners/1/writing/practices/{practice_id}")
        assert inspected.status_code == 200
        _seed_learner(engine, learner_id=2)
        hidden = client.get(f"/learners/2/writing/practices/{practice_id}")
        _assert_safe_error(hidden, status_code=404, code="practice_not_found")
        cross_owner = client.post(
            f"/learners/2/writing/practices/{practice_id}/submit", json={"essay": "Other learner."}
        )
        _assert_safe_error(cross_owner, status_code=409, code="practice_conflict")

        first = client.post(
            f"/learners/1/writing/practices/{practice_id}/submit", json={"essay": "Same essay."}
        )
        assert first.status_code == 200 and first.json()["status"] == "submitted"
        reused = client.post(
            f"/learners/1/writing/practices/{practice_id}/submit", json={"essay": "Same essay."}
        )
        assert reused.status_code == 200 and reused.json()["status"] == "reused"
        conflict = client.post(
            f"/learners/1/writing/practices/{practice_id}/submit", json={"essay": "Different essay."}
        )
        assert conflict.status_code == 200 and conflict.json()["status"] == "conflict"
        assert len(provider.requests) == 1
    finally:
        client.app.dependency_overrides.clear()


def test_in_progress_and_completion_public_contract(client: TestClient, engine) -> None:
    practice_id, _ = _generate(client, _practice_recommendation_id(client, engine))
    provider = FakeProvider([])
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        before_submitted = client.post(f"/learners/1/writing/practices/{practice_id}/complete")
        _assert_safe_error(before_submitted, status_code=409, code="practice_conflict")
        with create_session_factory(engine)() as session:
            practice = session.get(WritingPractice, practice_id)
            assert practice is not None
            practice.lifecycle_state = "submission_in_progress"
            practice.submission_fingerprint = "f" * 64
            practice.claim_token = "test-claim"
            session.commit()
        in_progress = client.post(
            f"/learners/1/writing/practices/{practice_id}/submit", json={"essay": "In progress essay."}
        )
        assert in_progress.status_code == 200
        assert in_progress.json()["status"] == "in_progress"
        assert not provider.requests
    finally:
        client.app.dependency_overrides.clear()


def test_completion_success_replans_at_api_boundary(client: TestClient, engine) -> None:
    practice_id, _ = _generate(client, _practice_recommendation_id(client, engine))
    provider = FakeProvider([_payload()])
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        submitted = client.post(
            f"/learners/1/writing/practices/{practice_id}/submit", json={"essay": "Completion essay."}
        )
        assert submitted.status_code == 200
        completed = client.post(f"/learners/1/writing/practices/{practice_id}/complete")
        assert completed.status_code == 200
        assert completed.json()["next_recommendation"]["decision_type"] in {"practice", "no_practice"}
    finally:
        client.app.dependency_overrides.clear()


def test_phase4_persistence_and_authority_errors_use_safe_api_contract(
    client: TestClient, monkeypatch
) -> None:
    async def generation_authority_failure(*_args, **_kwargs):
        raise GeneratedPracticeAuthorityError("raw generator mismatch")

    async def generation_persistence_failure(*_args, **_kwargs):
        raise PracticeGenerationPersistenceError("raw SQL boom")

    async def submission_persistence_failure(*_args, **_kwargs):
        raise PracticeSubmissionPersistenceError("raw token fingerprint essay")

    def completion_persistence_failure(*_args, **_kwargs):
        raise PracticeCompletionPersistenceError("raw database question")

    client.app.dependency_overrides[get_practice_generator] = lambda: FakePracticeGenerator()
    client.app.dependency_overrides[get_writing_provider] = lambda: FakeProvider([])
    try:
        monkeypatch.setattr(PracticeGenerationService, "generate_or_resolve", generation_authority_failure)
        authority = client.post("/learners/1/writing/recommendations/1/practice")
        _assert_safe_error(authority, status_code=502, code="provider_invalid_response")

        monkeypatch.setattr(PracticeGenerationService, "generate_or_resolve", generation_persistence_failure)
        generation = client.post("/learners/1/writing/recommendations/1/practice")
        _assert_safe_error(generation, status_code=503, code="persistence_unavailable")

        monkeypatch.setattr(PracticeSubmissionService, "submit", submission_persistence_failure)
        submission = client.post("/learners/1/writing/practices/1/submit", json={"essay": "No leak."})
        _assert_safe_error(submission, status_code=503, code="persistence_unavailable")

        monkeypatch.setattr(PracticeCompletionService, "complete", completion_persistence_failure)
        completion = client.post("/learners/1/writing/practices/1/complete")
        _assert_safe_error(completion, status_code=503, code="persistence_unavailable")
    finally:
        client.app.dependency_overrides.clear()
