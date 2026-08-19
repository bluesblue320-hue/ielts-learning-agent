"""P7-05 integration coverage for decision-time exact-tie memory context."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import inspect

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import create_session_factory
from app.learner.memory_planning_policy import (
    MEMORY_CONTEXT_VERSION,
    PLANNER_SNAPSHOT_VERSION,
    PLANNER_V2_VERSION,
    PLANNING_RECENT_PRACTICE_WINDOW,
    SELECTION_TRACE_VERSION,
)
from app.learner.memory_planning_context import (
    PlanningContextOwnerNotFoundError,
    build_memory_aware_planning_context,
)
from app.models.learning import LearningUpdate
from tests.test_learning_api import _seed_learner, client, engine
from tests.test_memory_queries import (
    _complete_targeted_practice,
    _seed_full_evaluation,
)


pytestmark = [pytest.mark.integration]

DT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_frozen_planner_context_policy_constants() -> None:
    assert PLANNER_V2_VERSION == "writing-practice-gap-memory-v2"
    assert MEMORY_CONTEXT_VERSION == "writing-memory-aware-planning-context-v1"
    assert SELECTION_TRACE_VERSION == "writing-planner-selection-trace-v1"
    assert PLANNER_SNAPSHOT_VERSION == "writing-practice-gap-memory-v2-audit-v1"
    assert PLANNING_RECENT_PRACTICE_WINDOW == 3

def _apply(
    client: TestClient,
    engine,
    *,
    evaluation_id: int,
    attempt_id: int,
    created_at: datetime,
    task_response: str = "6.0",
) -> int:
    _seed_full_evaluation(
        engine,
        evaluation_id=evaluation_id,
        attempt_id=attempt_id,
        created_at=created_at,
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


def _context(engine, *, owner_update_id: int):
    with create_session_factory(engine)() as session:
        return build_memory_aware_planning_context(
            session,
            learner_id=1,
            current_target_band=Decimal("7.0"),
            owner_learning_update_id=owner_update_id,
        )


def test_current_initial_update_occupies_planning_recency_window(
    client: TestClient,
    engine,
) -> None:
    _seed_learner(engine)
    owner = _apply(
        client,
        engine,
        evaluation_id=200,
        attempt_id=100,
        created_at=DT,
    )

    context = _context(engine, owner_update_id=owner)
    for skill in (
        "task_response",
        "coherence_and_cohesion",
        "lexical_resource",
        "grammatical_range_and_accuracy",
    ):
        item = getattr(context.skills, skill)
        assert item.recent_practice_source_episode_ids == [owner]
        assert item.recent_practice_count == 0
        assert item.source_episode_ids == [owner]


def test_current_targeted_update_counts_its_actual_practice_target(
    client: TestClient,
    engine,
) -> None:
    _seed_learner(engine)
    initial = _apply(
        client,
        engine,
        evaluation_id=200,
        attempt_id=100,
        created_at=DT,
    )
    completion = _complete_targeted_practice(client, engine)
    owner = completion["learning_update_id"]

    context = _context(engine, owner_update_id=owner)
    assert context.skills.task_response.recent_practice_source_episode_ids == [
        owner,
        initial,
    ]
    assert context.skills.task_response.recent_practice_count == 1
    assert context.skills.coherence_and_cohesion.recent_practice_count == 0


def test_observation_provenance_uses_frozen_canonical_chronology(
    client: TestClient,
    engine,
) -> None:
    _seed_learner(engine)
    first = _apply(
        client,
        engine,
        evaluation_id=200,
        attempt_id=100,
        created_at=DT + timedelta(minutes=2),
        task_response="6.0",
    )
    second = _apply(
        client,
        engine,
        evaluation_id=201,
        attempt_id=101,
        created_at=DT + timedelta(minutes=1),
        task_response="7.0",
    )
    third = _apply(
        client,
        engine,
        evaluation_id=202,
        attempt_id=102,
        created_at=DT + timedelta(minutes=3),
        task_response="6.5",
    )

    context = _context(engine, owner_update_id=third)
    task_response = context.skills.task_response
    assert task_response.trend == "declining"
    assert task_response.source_observation_ids == [5, 1, 9]
    assert task_response.source_episode_ids == [second, first, third]
    # Planner recency is intentionally a separate accepted-update order.
    assert task_response.recent_practice_source_episode_ids == [third, second, first]


def test_historical_owner_bounds_evidence_and_accepted_update_recency(
    client: TestClient,
    engine,
) -> None:
    _seed_learner(engine)
    first = _apply(
        client,
        engine,
        evaluation_id=200,
        attempt_id=100,
        created_at=DT,
    )
    owner = _apply(
        client,
        engine,
        evaluation_id=201,
        attempt_id=101,
        created_at=DT + timedelta(minutes=1),
    )
    _apply(
        client,
        engine,
        evaluation_id=202,
        attempt_id=102,
        created_at=DT + timedelta(minutes=2),
    )
    _apply(
        client,
        engine,
        evaluation_id=203,
        attempt_id=103,
        created_at=DT + timedelta(minutes=3),
    )

    context = _context(engine, owner_update_id=owner)
    item = context.skills.task_response
    assert item.recent_practice_source_episode_ids == [owner, first]
    assert item.source_episode_ids == [first, owner]

    with create_session_factory(engine)() as session:
        owner_row = session.scalar(
            select(LearningUpdate).where(LearningUpdate.id == owner)
        )
        assert owner_row is not None
        owner_row.created_at = DT + timedelta(days=1)
        session.commit()
    # Accepted update id, not transaction/default timestamp, remains decisive.
    assert _context(engine, owner_update_id=owner).skills.task_response.recent_practice_source_episode_ids == [
        owner,
        first,
    ]


def test_owner_must_belong_to_learner(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _seed_learner(engine, learner_id=2)
    owner = _apply(
        client,
        engine,
        evaluation_id=200,
        attempt_id=100,
        created_at=DT,
    )

    with create_session_factory(engine)() as session:
        with pytest.raises(PlanningContextOwnerNotFoundError):
            build_memory_aware_planning_context(
                session,
                learner_id=2,
                current_target_band=Decimal("7.0"),
                owner_learning_update_id=owner,
            )


def test_builder_has_no_episode_or_recommendation_dependency() -> None:
    import app.learner.memory_planning_context as context_module

    source = inspect.getsource(context_module)
    assert "list_learner_episodes" not in source
    assert "PracticeRecommendation" not in source
    assert "LearningUpdate.created_at" not in source
