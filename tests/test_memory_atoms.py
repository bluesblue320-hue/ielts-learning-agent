"""P6-05 L1 atom derivation tests.

Pure tests use lightweight row fakes; the ``practice_completed`` tests run
against isolated PostgreSQL because the derivation resolves the persisted
practice -> attempt -> evaluation -> learning-update chain.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import create_session_factory
from app.memory.atoms import (
    derive_practice_completed,
    recommendation_observation_atom,
    skill_observation_atom,
    target_snapshot_atom,
)
from app.models.learning import PracticeRecommendation
from app.schemas.learner import LearnerSkillStateSet
from app.schemas.planning import PracticeRecommendationDecision
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_learning_api import _seed_learner, client, engine
from tests.test_memory_queries import _apply_initial, _complete_targeted_practice
from tests.test_memory_schemas import build_states
from tests.test_practice_submission import _payload

DT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _evidence_row(**overrides) -> SimpleNamespace:
    values = {
        "id": 5,
        "skill": "lexical_resource",
        "observed_band": Decimal("6.5"),
        "learning_update_id": 7,
        "writing_evaluation_id": 200,
        "source_attempt_id": 100,
        "source_created_at": DT,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_skill_observation_atom_projection() -> None:
    atom = skill_observation_atom(_evidence_row())
    assert atom.atom_kind == "skill_observation"
    assert atom.skill == "lexical_resource"
    assert atom.observed_band.value == Decimal("6.5")
    assert atom.learning_evidence_id == 5
    assert atom.learning_update_id == 7
    assert atom.writing_evaluation_id == 200
    assert atom.source_attempt_id == 100
    assert atom.source_created_at == DT


def test_skill_observation_atom_rejects_missing_source() -> None:
    with pytest.raises(ValidationError):
        skill_observation_atom(_evidence_row(id=None))  # no source id -> invalid


def test_target_snapshot_atom_uses_recommendation_band_only() -> None:
    row = SimpleNamespace(
        id=11,
        learning_update_id=7,
        learner_target_band=Decimal("7.0"),
    )
    atom = target_snapshot_atom(row)
    assert atom is not None
    assert atom.historical_target_band.value == Decimal("7.0")
    assert atom.recommendation_id == 11
    assert atom.learning_update_id == 7
    # No current-target fallback field exists on the atom.


def test_target_snapshot_atom_none_for_target_unset() -> None:
    row = SimpleNamespace(id=11, learning_update_id=7, learner_target_band=None)
    assert target_snapshot_atom(row) is None


def test_recommendation_observation_atom() -> None:
    states = build_states(
        {"task_response": "6.0", "coherence_and_cohesion": "6.5", "lexical_resource": "6.5", "grammatical_range_and_accuracy": "6.5"}
    )
    decision = PracticeRecommendationDecision.model_validate(
        {
            "decision_type": "practice",
            "target_skill": "task_response",
            "learner_target_band": {"value": "7.0"},
            "current_estimate": "6.00",
            "reason_codes": ["largest_target_gap"],
            "planner_version": "writing-practice-gap-v1",
            "state_snapshot": states.model_dump(mode="json"),
        }
    )
    row = SimpleNamespace(
        id=11,
        learning_update_id=7,
        decision_type="practice",
        target_skill="task_response",
        learner_target_band=Decimal("7.0"),
        current_estimate=Decimal("6.00"),
        reason_codes=["largest_target_gap"],
        planner_version="writing-practice-gap-v1",
        state_snapshot=states.model_dump(mode="json"),
    )
    atom = recommendation_observation_atom(row, decision=decision)
    assert atom.atom_kind == "recommendation_observation"
    assert atom.recommendation_id == 11
    assert atom.learning_update_id == 7
    assert atom.decision.decision_type.value == "practice"


def test_practice_completed_not_for_generated(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation is not None
        recommendation_id = recommendation.id
    generator = FakePracticeGenerator()
    client.app.dependency_overrides[get_practice_generator] = lambda: generator
    try:
        generated = client.post(
            f"/learners/1/writing/recommendations/{recommendation_id}/practice"
        )
        assert generated.status_code == 200
        practice_id = generated.json()["practice"]["id"]
    finally:
        client.app.dependency_overrides.clear()
    with create_session_factory(engine)() as session:
        from app.models.practice import WritingPractice

        practice = session.get(WritingPractice, practice_id)
        assert practice is not None
        assert derive_practice_completed(session, practice=practice) is None


def test_practice_completed_after_submit_and_apply(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    result = _complete_targeted_practice(client, engine)
    with create_session_factory(engine)() as session:
        from app.models.practice import WritingPractice

        practice = session.get(WritingPractice, result["practice_id"])
        assert practice is not None
        atom = derive_practice_completed(session, practice=practice)
    assert atom is not None
    assert atom.atom_kind == "practice_completed"
    assert atom.writing_practice_id == result["practice_id"]
    assert atom.learning_update_id == result["learning_update_id"]
    assert atom.writing_evaluation_id == result["evaluation_id"]
    assert atom.attempt_id == result["attempt_id"]
    # completed_at is the applied LearningUpdate.created_at (no fallback).
    with create_session_factory(engine)() as session:
        from app.models.learning import LearningUpdate

        update = session.get(LearningUpdate, result["learning_update_id"])
        assert update is not None
        assert atom.completed_at == update.created_at


def test_practice_completed_none_for_submitted_but_unapplied(client: TestClient, engine) -> None:
    _seed_learner(engine, learner_id=1)
    _apply_initial(client, engine)
    with create_session_factory(engine)() as session:
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation is not None
        recommendation_id = recommendation.id
    generator = FakePracticeGenerator()
    provider = FakeProvider([_payload()])
    client.app.dependency_overrides[get_practice_generator] = lambda: generator
    client.app.dependency_overrides[get_writing_provider] = lambda: provider
    try:
        generated = client.post(
            f"/learners/1/writing/recommendations/{recommendation_id}/practice"
        )
        practice_id = generated.json()["practice"]["id"]
        submitted = client.post(
            f"/learners/1/writing/practices/{practice_id}/submit",
            json={"essay": "A submitted but not yet applied practice essay."},
        )
        assert submitted.json()["status"] == "submitted"
    finally:
        client.app.dependency_overrides.clear()
    with create_session_factory(engine)() as session:
        from app.models.practice import WritingPractice

        practice = session.get(WritingPractice, practice_id)
        assert practice is not None
        assert practice.lifecycle_state == "submitted"
        assert derive_practice_completed(session, practice=practice) is None
