"""P6-04 L0 episode query-layer integration tests (isolated PostgreSQL)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import create_session_factory
from app.memory.episode_queries import (
    get_learner_episode,
    list_learner_episodes,
)
from app.memory.errors import EpisodeNotFoundError
from app.models.learning import LearningUpdate, PracticeRecommendation
from app.models.writing import WritingAttempt, WritingEvaluation
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_learning_api import (
    _seed_learner,
    client,
    engine,
)
from tests.test_practice_submission import _payload

DT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _seed_full_evaluation(
    engine,
    *,
    evaluation_id: int = 200,
    attempt_id: int = 100,
    created_at: datetime = DT,
    bands: dict[str, str] | None = None,
) -> None:
    """Seed one attempt + evaluation with realistic criteria feedback (no learner)."""
    if bands is None:
        bands = {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    criteria_feedback = {
        skill: {"evidence": ["Evidence."], "feedback": "Feedback."}
        for skill in ("task_response", "coherence_and_cohesion", "lexical_resource", "grammatical_range_and_accuracy")
    }
    session_factory = create_session_factory(engine)
    with session_factory() as session:
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
                criteria_feedback=criteria_feedback,
                strengths=["Strength."],
                weaknesses=["Weakness."],
                error_tags=[],
                recommended_skills=[],
                feedback="Overall feedback.",
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


def _apply_initial(
    client: TestClient,
    engine,
    *,
    learner_id: int = 1,
    evaluation_id: int = 200,
    attempt_id: int = 100,
    created_at: datetime = DT,
) -> int:
    _seed_full_evaluation(
        engine,
        evaluation_id=evaluation_id,
        attempt_id=attempt_id,
        created_at=created_at,
    )
    response = client.post(
        f"/learners/{learner_id}/writing/evaluations/{evaluation_id}/apply"
    )
    assert response.status_code == 200
    return response.json()["learning_update_id"]


def _complete_targeted_practice(
    client: TestClient,
    engine,
    *,
    learner_id: int = 1,
) -> dict[str, object]:
    with create_session_factory(engine)() as session:
        recommendation = session.scalar(
            select(PracticeRecommendation).where(
                PracticeRecommendation.learner_id == learner_id
            )
        )
        assert recommendation is not None
        recommendation_id = recommendation.id
    generator = FakePracticeGenerator()
    provider = FakeProvider([_payload()])
    client.app.dependency_overrides[get_practice_generator] = lambda: generator
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        generated = client.post(
            f"/learners/{learner_id}/writing/recommendations/{recommendation_id}/practice"
        )
        assert generated.status_code == 200
        practice_id = generated.json()["practice"]["id"]
        submitted = client.post(
            f"/learners/{learner_id}/writing/practices/{practice_id}/submit",
            json={"essay": "A targeted practice essay with sufficient detail."},
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "submitted"
        completed = client.post(
            f"/learners/{learner_id}/writing/practices/{practice_id}/complete"
        )
        assert completed.status_code == 200
        return completed.json()
    finally:
        client.app.dependency_overrides.pop(get_practice_generator, None)
        client.app.dependency_overrides.pop(get_writing_provider, None)


def test_empty_learner_history_is_empty(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    with create_session_factory(engine)() as session:
        episodes = list_learner_episodes(session, learner_id=1)
    assert episodes == []


def test_history_deterministic_order_and_id_tie_break(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    first = _apply_initial(
        client, engine, evaluation_id=200, attempt_id=100, created_at=DT
    )
    second = _apply_initial(
        client, engine, evaluation_id=201, attempt_id=101, created_at=DT + timedelta(minutes=1)
    )
    third = _apply_initial(
        client, engine, evaluation_id=202, attempt_id=102, created_at=DT + timedelta(minutes=2)
    )
    with create_session_factory(engine)() as session:
        episodes = list_learner_episodes(session, learner_id=1)
    assert [e.episode_id for e in episodes] == [third, second, first]
    # occurred_at is the DB-assigned LearningUpdate.created_at; the frozen
    # deterministic ordering key is (created_at DESC, id DESC).
    assert all(e.occurred_at.tzinfo is not None for e in episodes)

    # Same created_at: id DESC is the deterministic tie-breaker.
    with create_session_factory(engine)() as session:
        first_row = session.get(LearningUpdate, first)
        third_row = session.get(LearningUpdate, third)
        assert first_row is not None and third_row is not None
        first_row.created_at = third_row.created_at  # exact tie on created_at
        session.commit()
    with create_session_factory(engine)() as session:
        episodes = list_learner_episodes(session, learner_id=1)
    assert [e.episode_id for e in episodes] == [third, first, second]


def test_episode_type_initial_writing(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    with create_session_factory(engine)() as session:
        episodes = list_learner_episodes(session, learner_id=1)
    assert len(episodes) == 1
    assert episodes[0].episode_type == "initial_writing"
    assert episodes[0].writing_practice_id is None
    # occurred_at is the DB-assigned LearningUpdate.created_at (not the seed DT).
    assert episodes[0].occurred_at.tzinfo is not None


def test_episode_type_targeted_practice(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    result = _complete_targeted_practice(client, engine)
    with create_session_factory(engine)() as session:
        episodes = list_learner_episodes(session, learner_id=1)
    assert len(episodes) == 2
    latest = episodes[0]
    assert latest.episode_type == "targeted_practice"
    assert latest.writing_practice_id is not None
    assert latest.episode_id == result["learning_update_id"]
    assert episodes[1].episode_type == "initial_writing"


def test_episode_detail_full_provenance(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    episode_id = _apply_initial(client, engine)
    with create_session_factory(engine)() as session:
        detail = get_learner_episode(session, learner_id=1, episode_id=episode_id)
    assert detail.episode.episode_id == episode_id
    assert detail.episode.episode_type == "initial_writing"
    assert detail.episode.occurred_at == detail.learning_update.created_at
    assert detail.learning_update.learner_id == 1
    assert detail.learning_update.id == episode_id
    assert detail.attempt.question == "Q"
    assert detail.attempt.essay == "E"
    assert detail.attempt.word_count == 1
    assert detail.attempt.created_at == DT
    assert detail.evaluation.attempt_id == detail.attempt.attempt_id
    assert detail.evaluation.evaluation.product_band.value == Decimal("6.5")
    assert len(detail.evidence) == 4
    assert {item.skill for item in detail.evidence} == {
        "task_response",
        "coherence_and_cohesion",
        "lexical_resource",
        "grammatical_range_and_accuracy",
    }
    assert detail.recommendation.decision_type.value == "practice"
    assert detail.practice is None


def test_episode_detail_includes_linked_practice(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    result = _complete_targeted_practice(client, engine)
    with create_session_factory(engine)() as session:
        detail = get_learner_episode(
            session, learner_id=1, episode_id=result["learning_update_id"]
        )
    assert detail.episode.episode_type == "targeted_practice"
    assert detail.practice is not None
    assert detail.practice.id == result["practice_id"]
    assert detail.practice.attempt_id == result["attempt_id"]
    assert detail.evaluation.evaluation_id == result["evaluation_id"]


def test_cross_owner_protection(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _seed_learner(engine, learner_id=2)
    episode_id = _apply_initial(client, engine, learner_id=1)
    with create_session_factory(engine)() as session:
        with pytest.raises(EpisodeNotFoundError):
            get_learner_episode(session, learner_id=2, episode_id=episode_id)
        assert list_learner_episodes(session, learner_id=2) == []


def test_missing_episode_raises(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    with create_session_factory(engine)() as session:
        with pytest.raises(EpisodeNotFoundError):
            get_learner_episode(session, learner_id=1, episode_id=9999)
