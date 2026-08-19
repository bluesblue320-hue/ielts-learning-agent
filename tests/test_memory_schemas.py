"""P6-03 boundary tests for Phase 6 memory read schemas.

These tests encode the frozen P6-02/P6-03 schema decisions: strict
``extra="forbid"`` boundaries, positive persisted ids, strict episode-type /
trend / resume-action literals, band and derived-state validation, historical
vs current target separation, no invented persistent memory ids, and explicit
nullable boundary states. They exercise no ORM, service, route, or LLM
behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.learner import (
    LearnerSkillState,
    LearnerSkillStateSet,
    WritingSkillKey,
)
from app.schemas.memory import (
    LearningEpisodeSummary,
    PracticeCompletedAtom,
    SkillObservationAtom,
    SkillProgress,
    TargetSnapshotAtom,
    WritingContextResponse,
    WritingHistoryResponse,
    WritingProgressResponse,
)

DT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

ALL_FOUR: tuple[WritingSkillKey, ...] = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)


def _state(skill: str, band: str | None, count: int, learner_id: int = 1) -> LearnerSkillState:
    observed = band is not None
    return LearnerSkillState(
        learner_id=learner_id,
        skill=skill,
        estimated_band=Decimal(band) if observed else None,
        evidence_count=count if observed else 0,
        last_evidence_id=1 if observed else None,
        state_policy_version="writing-state-ewma-v1",
        revision=1 if observed else 0,
        updated_at=DT,
    )


def build_states(
    bands: dict[str, str | None],
    counts: dict[str, int] | None = None,
    learner_id: int = 1,
) -> LearnerSkillStateSet:
    counts = counts or {}
    return LearnerSkillStateSet(
        task_response=_state("task_response", bands["task_response"], counts.get("task_response", 3), learner_id),
        coherence_and_cohesion=_state(
            "coherence_and_cohesion", bands["coherence_and_cohesion"], counts.get("coherence_and_cohesion", 3), learner_id
        ),
        lexical_resource=_state("lexical_resource", bands["lexical_resource"], counts.get("lexical_resource", 3), learner_id),
        grammatical_range_and_accuracy=_state(
            "grammatical_range_and_accuracy",
            bands["grammatical_range_and_accuracy"],
            counts.get("grammatical_range_and_accuracy", 3),
            learner_id,
        ),
    )


def _observation(skill: str, band: str, evidence_id: int = 1) -> dict[str, object]:
    return {
        "skill": skill,
        "observed_band": {"value": band},
        "learning_evidence_id": evidence_id,
        "source_attempt_id": 100,
        "source_created_at": DT.isoformat(),
    }


def _summary_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "episode_id": 7,
        "episode_type": "initial_writing",
        "occurred_at": DT.isoformat(),
        "writing_evaluation_id": 200,
        "attempt_id": 100,
        "writing_practice_id": None,
        "recommendation_id": 11,
        "recommendation_decision_type": "practice",
        "recommendation_target_skill": "task_response",
        "recommendation_reason_codes": ["largest_target_gap"],
        "planner_version": "writing-practice-gap-v1",
        "skill_observations": {
            skill: _observation(skill, "6.5" if skill != "task_response" else "6.0", i + 1)
            for i, skill in enumerate(ALL_FOUR)
        },
    }
    payload.update(overrides)
    return payload


def test_episode_summary_valid_and_strict() -> None:
    summary = LearningEpisodeSummary.model_validate(_summary_payload())
    assert summary.episode_id == 7
    assert summary.episode_type == "initial_writing"
    assert summary.skill_observations.task_response.observed_band.value == Decimal("6.0")

    with pytest.raises(ValidationError):
        LearningEpisodeSummary.model_validate(_summary_payload(extra_field="x"))
    with pytest.raises(ValidationError):
        LearningEpisodeSummary.model_validate(_summary_payload(episode_id=0))
    with pytest.raises(ValidationError):
        LearningEpisodeSummary.model_validate(_summary_payload(episode_type="bad_type"))
    with pytest.raises(ValidationError):
        LearningEpisodeSummary.model_validate(_summary_payload(occurred_at="not-a-date"))


def test_episode_summary_band_and_practice_id_validation() -> None:
    with pytest.raises(ValidationError):
        LearningEpisodeSummary.model_validate(_summary_payload(writing_practice_id=-1))
    bad_band = _summary_payload()
    bad_band["skill_observations"]["task_response"]["observed_band"] = {"value": "6.3"}
    with pytest.raises(ValidationError):
        LearningEpisodeSummary.model_validate(bad_band)
    targeted = LearningEpisodeSummary.model_validate(
        _summary_payload(episode_type="targeted_practice", writing_practice_id=55)
    )
    assert targeted.episode_type == "targeted_practice"
    assert targeted.writing_practice_id == 55


def test_history_response_boundary() -> None:
    history = WritingHistoryResponse.model_validate(
        {
            "learner_id": 1,
            "episodes": [_summary_payload(), _summary_payload(episode_id=6, episode_type="targeted_practice", writing_practice_id=55)],
        }
    )
    assert len(history.episodes) == 2
    assert history.episodes[1].episode_type == "targeted_practice"
    with pytest.raises(ValidationError):
        WritingHistoryResponse.model_validate({"learner_id": 1, "episodes": [_summary_payload()], "extra": 1})


def test_skill_progress_literals_and_derived_state() -> None:
    payload: dict[str, object] = {
        "learner_id": 1,
        "skill": "task_response",
        "policy_version": "writing-progress-v1",
        "current_estimate": "6.50",
        "evidence_count": 3,
        "trend": "improving",
        "persistent_gap": True,
        "persistent_gap_status": "established",
        "recent_observation_count": 3,
        "recent_practice_count": 1,
        "latest_observation_time": DT.isoformat(),
        "last_episode_id": 7,
        "source_observation_ids": [1, 2, 3],
        "source_episode_ids": [5, 6, 7],
    }
    progress = SkillProgress.model_validate(payload)
    assert progress.trend == "improving"
    assert progress.current_estimate == Decimal("6.50")

    for bad_trend in ("up", "0.25", ""):
        with pytest.raises(ValidationError):
            SkillProgress.model_validate({**payload, "trend": bad_trend})
    with pytest.raises(ValidationError):
        SkillProgress.model_validate({**payload, "persistent_gap_status": "unknown"})
    # Derived-state band must respect 0.01 precision (not a half-band contract).
    with pytest.raises(ValidationError):
        SkillProgress.model_validate({**payload, "current_estimate": "6.005"})
    with pytest.raises(ValidationError):
        SkillProgress.model_validate({**payload, "policy_version": "writing-progress-v9"})
    # No invented pattern id is accepted.
    with pytest.raises(ValidationError):
        SkillProgress.model_validate({**payload, "pattern_id": 99})


def test_target_snapshot_has_no_current_target_fallback() -> None:
    atom = TargetSnapshotAtom.model_validate(
        {
            "atom_kind": "target_snapshot",
            "learning_update_id": 7,
            "recommendation_id": 11,
            "historical_target_band": {"value": "7.0"},
        }
    )
    assert atom.historical_target_band.value == Decimal("7.0")
    # The atom must never carry the current learner target as a fallback.
    with pytest.raises(ValidationError):
        TargetSnapshotAtom.model_validate(
            {
                "atom_kind": "target_snapshot",
                "learning_update_id": 7,
                "recommendation_id": 11,
                "historical_target_band": {"value": "7.0"},
                "current_target_band": {"value": "7.0"},
            }
        )
    with pytest.raises(ValidationError):
        TargetSnapshotAtom.model_validate(
            {
                "atom_kind": "target_snapshot",
                "learning_update_id": 7,
                "recommendation_id": 11,
                "historical_target_band": {"value": "9.5"},
            }
        )


def test_skill_observation_atom_provenance() -> None:
    atom = SkillObservationAtom.model_validate(
        {
            "atom_kind": "skill_observation",
            "skill": "lexical_resource",
            "observed_band": {"value": "6.5"},
            "learning_evidence_id": 3,
            "learning_update_id": 7,
            "writing_evaluation_id": 200,
            "source_attempt_id": 100,
            "source_created_at": DT.isoformat(),
        }
    )
    assert atom.learning_evidence_id == 3
    assert atom.atom_kind == "skill_observation"
    # Provenance ids must be positive persisted ids.
    with pytest.raises(ValidationError):
        SkillObservationAtom.model_validate(
            {
                "atom_kind": "skill_observation",
                "skill": "lexical_resource",
                "observed_band": {"value": "6.5"},
                "learning_evidence_id": 0,
                "learning_update_id": 7,
                "writing_evaluation_id": 200,
                "source_attempt_id": 100,
                "source_created_at": DT.isoformat(),
            }
        )


def test_practice_completed_atom_requires_completed_at() -> None:
    atom = PracticeCompletedAtom.model_validate(
        {
            "atom_kind": "practice_completed",
            "skill": "task_response",
            "writing_practice_id": 55,
            "learning_update_id": 7,
            "writing_evaluation_id": 201,
            "attempt_id": 101,
            "completed_at": DT.isoformat(),
        }
    )
    assert atom.completed_at == DT
    with pytest.raises(ValidationError):
        PracticeCompletedAtom.model_validate(
            {
                "atom_kind": "practice_completed",
                "skill": "task_response",
                "writing_practice_id": 55,
                "learning_update_id": 7,
                "writing_evaluation_id": 201,
                "attempt_id": 101,
            }
        )


def _progress_payload(skill: str, *, band: str, trend: str, gap: bool = True) -> dict[str, object]:
    return {
        "learner_id": 1,
        "skill": skill,
        "policy_version": "writing-progress-v1",
        "current_estimate": band,
        "evidence_count": 3,
        "trend": trend,
        "persistent_gap": gap,
        "persistent_gap_status": "established",
        "recent_observation_count": 3,
        "recent_practice_count": 0,
        "latest_observation_time": DT.isoformat(),
        "last_episode_id": 7,
        "source_observation_ids": [1, 2, 3],
        "source_episode_ids": [5, 6, 7],
    }


def test_progress_response_includes_l2_and_l3() -> None:
    states = build_states(
        {"task_response": "6.0", "coherence_and_cohesion": "6.5", "lexical_resource": "6.5", "grammatical_range_and_accuracy": "6.5"}
    )
    response = WritingProgressResponse.model_validate(
        {
            "learner_id": 1,
            "current_writing_target_band": {"value": "7.0"},
            "current_state": states,
            "skills": {
                skill: SkillProgress.model_validate(_progress_payload(skill, band="6.00" if skill == "task_response" else "6.50", trend="improving" if skill == "task_response" else "stable"))
                for skill in ALL_FOUR
            },
            "memory_version": "writing-memory-v1",
            "progress_version": "writing-progress-v1",
        }
    )
    assert response.current_writing_target_band.value == Decimal("7.0")
    assert response.skills.task_response.trend == "improving"
    # L3 current-state reference is read, not duplicated as authoritative state.
    assert response.current_state.task_response.estimated_band == Decimal("6.00")
    # No invented profile id is accepted.
    with pytest.raises(ValidationError):
        WritingProgressResponse.model_validate(
            {
                "learner_id": 1,
                "current_writing_target_band": {"value": "7.0"},
                "current_state": states,
                "skills": {
                    skill: SkillProgress.model_validate(_progress_payload(skill, band="6.50", trend="stable"))
                    for skill in ALL_FOUR
                },
                "memory_version": "writing-memory-v1",
                "progress_version": "writing-progress-v1",
                "profile_id": 1,
            }
        )


def test_context_response_boundaries() -> None:
    states = build_states(
        {"task_response": "6.0", "coherence_and_cohesion": "6.5", "lexical_resource": "6.5", "grammatical_range_and_accuracy": "6.5"}
    )
    context = WritingContextResponse.model_validate(
        {
            "learner_id": 1,
            "resume_action": "initial_writing",
            "has_learner_owned_episodes": False,
            "latest_learning_update_id": None,
            "current_recommendation_id": None,
            "current_recommendation": None,
            "relevant_practice": None,
            "current_state": states,
        }
    )
    assert context.resume_action == "initial_writing"
    assert context.latest_learning_update_id is None

    for bad_action in ("initial-writing", "resume", "stop", ""):
        with pytest.raises(ValidationError):
            WritingContextResponse.model_validate(
                {
                    "learner_id": 1,
                    "resume_action": bad_action,
                    "has_learner_owned_episodes": True,
                    "latest_learning_update_id": 7,
                    "current_recommendation_id": 11,
                    "current_recommendation": None,
                    "relevant_practice": None,
                    "current_state": states,
                }
            )
