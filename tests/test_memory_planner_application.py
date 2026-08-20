"""P7-07 atomic apply integration for planner v2 and lazy Memory use."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.session import create_session_factory
from app.learner.memory_planning_context import PlanningContextPersistenceError
from app.models.learning import (
    LearnerSkillState,
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
)
from app.services.learning_application import (
    LearningPersistenceError,
    apply_writing_evaluation,
)
from tests.test_learning_api import _seed_learner, engine
from tests.test_memory_queries import _seed_full_evaluation


pytestmark = [pytest.mark.integration]


def _seed(
    engine,
    *,
    evaluation_id: int,
    attempt_id: int,
    bands: dict[str, str],
    target: str = "7.0",
) -> None:
    _seed_learner(engine, target=target)
    _seed_full_evaluation(
        engine,
        evaluation_id=evaluation_id,
        attempt_id=attempt_id,
        bands=bands,
    )


def _apply(engine, *, evaluation_id: int):
    with create_session_factory(engine)() as session:
        return apply_writing_evaluation(
            session,
            learner_id=1,
            writing_evaluation_id=evaluation_id,
        )


def _counts(engine) -> dict[str, int]:
    with create_session_factory(engine)() as session:
        return {
            "updates": session.scalar(select(func.count()).select_from(LearningUpdate)),
            "evidence": session.scalar(select(func.count()).select_from(LearningEvidence)),
            "states": session.scalar(select(func.count()).select_from(LearnerSkillState)),
            "recommendations": session.scalar(
                select(func.count()).select_from(PracticeRecommendation)
            ),
        }


def test_unique_gap_apply_uses_v2_without_memory_query(engine, monkeypatch) -> None:
    _seed(
        engine,
        evaluation_id=200,
        attempt_id=100,
        bands={
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("unique-gap apply must not build Memory context")

    monkeypatch.setattr(
        "app.services.learning_application.build_memory_aware_planning_context",
        fail_if_called,
    )
    result = _apply(engine, evaluation_id=200)
    assert result.reused is False
    assert result.recommendation.planner_version == "writing-practice-gap-memory-v2"
    assert result.recommendation.target_skill == "task_response"
    assert result.recommendation.reason_codes[0].value == "largest_target_gap"
    assert _counts(engine) == {
        "updates": 1,
        "evidence": 4,
        "states": 4,
        "recommendations": 1,
    }

    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        update = session.scalar(select(LearningUpdate))
        assert recommendation is not None and update is not None
        assert update.planner_version == "writing-practice-gap-memory-v2"
        assert recommendation.planner_context_snapshot is None


def test_no_practice_apply_uses_v2_without_memory_query(engine, monkeypatch) -> None:
    _seed(
        engine,
        evaluation_id=200,
        attempt_id=100,
        target="6.0",
        bands={skill: "6.0" for skill in (
            "task_response",
            "coherence_and_cohesion",
            "lexical_resource",
            "grammatical_range_and_accuracy",
        )},
    )
    monkeypatch.setattr(
        "app.services.learning_application.build_memory_aware_planning_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("no-practice apply must not build Memory context")
        ),
    )

    result = _apply(engine, evaluation_id=200)
    assert result.recommendation.planner_version == "writing-practice-gap-memory-v2"
    assert result.recommendation.decision_type.value == "no_practice"
    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation is not None
        assert recommendation.planner_context_snapshot is None


def test_exact_tie_apply_persists_internal_snapshot_and_replays_v2(engine) -> None:
    _seed(
        engine,
        evaluation_id=200,
        attempt_id=100,
        bands={
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
    )

    first = _apply(engine, evaluation_id=200)
    second = _apply(engine, evaluation_id=200)
    assert first.reused is False
    assert second.reused is True
    assert second.learning_update_id == first.learning_update_id
    assert second.recommendation_id == first.recommendation_id
    assert first.recommendation.planner_version == "writing-practice-gap-memory-v2"
    assert second.recommendation.planner_version == "writing-practice-gap-memory-v2"
    assert first.recommendation.target_skill == "task_response"
    assert _counts(engine) == {
        "updates": 1,
        "evidence": 4,
        "states": 4,
        "recommendations": 1,
    }

    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation is not None
        snapshot = recommendation.planner_context_snapshot
        assert snapshot is not None
        assert snapshot["snapshot_version"] == "writing-practice-gap-memory-v2-audit-v1"
        assert snapshot["selection_trace"]["initial_max_gap_candidates"] == [
            "task_response",
            "coherence_and_cohesion",
        ]
        assert snapshot["selection_trace"]["selected_skill"] == "task_response"
        assert snapshot["memory_context"]["skills"]["task_response"][
            "recent_practice_source_episode_ids"
        ] == [first.learning_update_id]


def test_exact_tie_context_failure_rolls_back_every_new_apply_write(
    engine,
    monkeypatch,
) -> None:
    _seed(
        engine,
        evaluation_id=200,
        attempt_id=100,
        bands={
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
    )

    def fail_context(*_args, **_kwargs):
        raise PlanningContextPersistenceError("unavailable")

    monkeypatch.setattr(
        "app.services.learning_application.build_memory_aware_planning_context",
        fail_context,
    )
    with pytest.raises(LearningPersistenceError, match="decision-time planning context"):
        _apply(engine, evaluation_id=200)
    assert _counts(engine) == {
        "updates": 0,
        "evidence": 0,
        "states": 0,
        "recommendations": 0,
    }
