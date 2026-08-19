"""P6-07 L3 learner profile read-model tests (isolated PostgreSQL)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import create_session_factory
from app.memory.profile import build_learner_progress
from app.models.learning import Learner
from app.services.learning_application import LearnerNotFoundError
from tests.test_learning_api import _seed_learner, client, engine
from tests.test_memory_queries import _apply_initial, _seed_full_evaluation

DT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _apply_with_bands(
    client: TestClient,
    engine,
    *,
    evaluation_id: int,
    attempt_id: int,
    task_response: str,
) -> int:
    _seed_full_evaluation(
        engine,
        evaluation_id=evaluation_id,
        attempt_id=attempt_id,
        bands={
            "task_response": task_response,
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
    )
    response = client.post(f"/learners/1/writing/evaluations/{evaluation_id}/apply")
    assert response.status_code == 200
    return response.json()["learning_update_id"]


def test_populated_learner_trend_and_gap(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    # Canonical task_response series: 6.0, 6.5, 7.0 -> improving; window all
    # below 7.0? The latest window [6.0, 6.5, 7.0] contains 7.0 (not < 7.0).
    _apply_with_bands(client, engine, evaluation_id=200, attempt_id=100, task_response="6.0")
    _apply_with_bands(client, engine, evaluation_id=201, attempt_id=101, task_response="6.5")
    _apply_with_bands(client, engine, evaluation_id=202, attempt_id=102, task_response="7.0")
    with create_session_factory(engine)() as session:
        progress = build_learner_progress(session, learner_id=1)
    assert progress.learner_id == 1
    assert progress.current_writing_target_band.value == Decimal("7.0")
    assert progress.memory_version == "writing-memory-v1"
    assert progress.progress_version == "writing-progress-v1"
    tr = progress.skills.task_response
    assert tr.trend == "improving"
    assert tr.persistent_gap is False
    assert tr.persistent_gap_status == "established"
    assert tr.evidence_count == 3
    assert tr.recent_observation_count == 3
    assert tr.latest_observation_time is not None
    assert tr.last_episode_id is not None
    # Current estimate is READ from the authoritative state engine (EWMA 6.63).
    assert tr.current_estimate == Decimal("6.63")
    assert tr.source_observation_ids == [1, 5, 9]


def test_current_estimate_reads_authoritative_state(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_with_bands(client, engine, evaluation_id=200, attempt_id=100, task_response="6.5")
    with create_session_factory(engine)() as session:
        progress = build_learner_progress(session, learner_id=1)
    # First observation: state estimate = the observed band itself (6.50).
    assert progress.skills.task_response.current_estimate == Decimal("6.50")
    assert progress.current_state.task_response.estimated_band == Decimal("6.50")


def test_insufficient_history(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_with_bands(client, engine, evaluation_id=200, attempt_id=100, task_response="6.0")
    with create_session_factory(engine)() as session:
        progress = build_learner_progress(session, learner_id=1)
    tr = progress.skills.task_response
    assert tr.trend == "insufficient_history"
    assert tr.persistent_gap is False
    assert tr.persistent_gap_status == "insufficient_history"
    assert tr.recent_observation_count == 1


def test_unobserved_learner(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    with create_session_factory(engine)() as session:
        progress = build_learner_progress(session, learner_id=1)
    for skill in (
        "task_response",
        "coherence_and_cohesion",
        "lexical_resource",
        "grammatical_range_and_accuracy",
    ):
        item = getattr(progress.skills, skill)
        assert item.current_estimate is None
        assert item.evidence_count == 0
        assert item.trend == "insufficient_history"
        assert item.persistent_gap is False
        assert item.persistent_gap_status == "insufficient_history"
        assert item.latest_observation_time is None
        assert item.last_episode_id is None
    assert progress.current_state.task_response.evidence_count == 0


def test_persistent_gap_all_below_target(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    # Series 6.0, 6.0, 6.5: all below 7.0 -> persistent_gap true, improving.
    _apply_with_bands(client, engine, evaluation_id=200, attempt_id=100, task_response="6.0")
    _apply_with_bands(client, engine, evaluation_id=201, attempt_id=101, task_response="6.0")
    _apply_with_bands(client, engine, evaluation_id=202, attempt_id=102, task_response="6.5")
    with create_session_factory(engine)() as session:
        progress = build_learner_progress(session, learner_id=1)
    tr = progress.skills.task_response
    assert tr.trend == "improving"
    assert tr.persistent_gap is True
    assert tr.persistent_gap_status == "established"


def test_traceability_and_determinism(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_with_bands(client, engine, evaluation_id=200, attempt_id=100, task_response="6.0")
    _apply_with_bands(client, engine, evaluation_id=201, attempt_id=101, task_response="6.5")
    _apply_with_bands(client, engine, evaluation_id=202, attempt_id=102, task_response="7.0")
    with create_session_factory(engine)() as session:
        first = build_learner_progress(session, learner_id=1)
    with create_session_factory(engine)() as session:
        second = build_learner_progress(session, learner_id=1)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    # Drill-down source ids are real persisted evidence ids (task_response
    # evidence is inserted first per apply: ids 1, 5, 9).
    assert first.skills.task_response.source_observation_ids == [1, 5, 9]
    assert first.skills.task_response.last_episode_id == 3


def test_learner_not_found(client: TestClient, engine) -> None:
    with create_session_factory(engine)() as session:
        try:
            build_learner_progress(session, learner_id=99)
            raise AssertionError("expected LearnerNotFoundError")
        except LearnerNotFoundError:
            pass
