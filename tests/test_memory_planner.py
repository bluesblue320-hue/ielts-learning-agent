"""Focused normative tests for the pure Phase 7 planner v2."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import inspect

import pytest

from app.learner.memory_planner import (
    plan_practice_v2,
    select_practice_v2_base,
)
from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillState, LearnerSkillStateSet
from app.schemas.planning import MemoryAwarePlanningContext


DT = datetime(2026, 1, 1, 12, 0, 0)
SKILLS = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)


def _states(
    bands: dict[str, str | None],
    counts: dict[str, int] | None = None,
) -> LearnerSkillStateSet:
    counts = counts or {}
    return LearnerSkillStateSet(
        **{
            skill: LearnerSkillState(
                learner_id=1,
                skill=skill,
                estimated_band=(Decimal(bands[skill]) if bands[skill] else None),
                evidence_count=counts.get(skill, 3) if bands[skill] else 0,
                last_evidence_id=1 if bands[skill] else None,
                state_policy_version="writing-state-ewma-v1",
                revision=1 if bands[skill] else 0,
                updated_at=DT,
            )
            for skill in SKILLS
        }
    )


def _target(value: str = "7.0") -> BandScore:
    return BandScore(value=Decimal(value))


def _context(
    *,
    trends: dict[str, str] | None = None,
    persistent: dict[str, bool] | None = None,
    persistent_status: dict[str, str] | None = None,
    recent: dict[str, int] | None = None,
) -> MemoryAwarePlanningContext:
    trends = trends or {}
    persistent = persistent or {}
    persistent_status = persistent_status or {}
    recent = recent or {}
    return MemoryAwarePlanningContext.model_validate(
        {
            "memory_version": "writing-memory-v1",
            "progress_version": "writing-progress-v1",
            "memory_context_version": "writing-memory-aware-planning-context-v1",
            "skills": {
                skill: {
                    "skill": skill,
                    "trend": trends.get(skill, "stable"),
                    "persistent_gap": persistent.get(skill, False),
                    "persistent_gap_status": persistent_status.get(
                        skill, "established"
                    ),
                    "recent_practice_count": recent.get(skill, 0),
                    "source_observation_ids": [1, 2, 3],
                    "source_episode_ids": [1, 2, 3],
                    "recent_practice_source_episode_ids": [3, 2, 1],
                }
                for skill in SKILLS
            },
        }
    )


def _tie_states() -> LearnerSkillStateSet:
    return _states(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    )


def _reason_values(result) -> list[str]:
    return [reason.value for reason in result.decision.reason_codes]


def test_terminal_branches_and_unique_gap_never_require_memory() -> None:
    cold = _states({skill: None for skill in SKILLS})
    cold_result = plan_practice_v2(learner_target_band=_target(), states=cold)
    assert cold_result.decision.planner_version == "writing-practice-gap-memory-v2"
    assert cold_result.decision.reason_codes[0].value == "cold_start"
    assert cold_result.selection_trace is None

    unique = _states(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    base = select_practice_v2_base(learner_target_band=_target(), states=unique)
    assert base.requires_memory_context is False
    result = plan_practice_v2(learner_target_band=_target(), states=unique)
    assert result.decision.target_skill == "task_response"
    assert _reason_values(result) == ["largest_target_gap"]
    assert result.selection_trace is None

    with pytest.raises(ValueError, match="must not receive memory context"):
        plan_practice_v2(
            learner_target_band=_target(),
            states=unique,
            memory_context=_context(),
        )


def test_exact_tie_requires_context_and_persistent_gap_resolves_first() -> None:
    base = select_practice_v2_base(learner_target_band=_target(), states=_tie_states())
    assert base.requires_memory_context is True
    assert base.exact_max_gap_candidates == (
        "task_response",
        "coherence_and_cohesion",
    )
    with pytest.raises(ValueError, match="require memory context"):
        plan_practice_v2(learner_target_band=_target(), states=_tie_states())

    result = plan_practice_v2(
        learner_target_band=_target(),
        states=_tie_states(),
        memory_context=_context(persistent={"coherence_and_cohesion": True}),
    )
    assert result.decision.target_skill == "coherence_and_cohesion"
    assert _reason_values(result) == ["largest_target_gap"]
    assert result.selection_trace is not None
    assert [stage.stage for stage in result.selection_trace.stages] == [
        "persistent_gap"
    ]
    assert result.selection_trace.stages[0].narrowed is True


def test_insufficient_persistent_gap_does_not_qualify_and_trace_records_noop() -> None:
    result = plan_practice_v2(
        learner_target_band=_target(),
        states=_tie_states(),
        memory_context=_context(
            persistent={"coherence_and_cohesion": True},
            persistent_status={"coherence_and_cohesion": "insufficient_history"},
        ),
    )
    assert result.decision.target_skill == "task_response"
    assert _reason_values(result) == ["largest_target_gap", "priority_tiebreak"]
    assert result.selection_trace is not None
    assert [stage.narrowed for stage in result.selection_trace.stages] == [
        False,
        False,
        False,
        True,
    ]
    assert result.selection_trace.stages[0].candidates_before == [
        "task_response",
        "coherence_and_cohesion",
    ]
    assert result.selection_trace.stages[0].candidates_after == [
        "task_response",
        "coherence_and_cohesion",
    ]


def test_trend_requires_established_history_for_every_remaining_candidate() -> None:
    established = plan_practice_v2(
        learner_target_band=_target(),
        states=_tie_states(),
        memory_context=_context(
            trends={
                "task_response": "declining",
                "coherence_and_cohesion": "improving",
            }
        ),
    )
    assert established.decision.target_skill == "task_response"
    assert _reason_values(established) == ["largest_target_gap"]
    assert [stage.stage for stage in established.selection_trace.stages] == [
        "persistent_gap",
        "trend",
    ]

    insufficient = plan_practice_v2(
        learner_target_band=_target(),
        states=_tie_states(),
        memory_context=_context(
            trends={
                "task_response": "declining",
                "coherence_and_cohesion": "insufficient_history",
            },
            recent={"task_response": 1, "coherence_and_cohesion": 0},
        ),
    )
    assert insufficient.decision.target_skill == "coherence_and_cohesion"
    assert _reason_values(insufficient) == ["largest_target_gap"]
    assert insufficient.selection_trace.stages[1].narrowed is False
    assert insufficient.selection_trace.stages[2].stage == "recent_practice"
    assert insufficient.selection_trace.stages[2].narrowed is True


def test_recent_practice_then_canonical_priority_have_frozen_semantics() -> None:
    recency = plan_practice_v2(
        learner_target_band=_target(),
        states=_tie_states(),
        memory_context=_context(recent={"task_response": 2, "coherence_and_cohesion": 0}),
    )
    assert recency.decision.target_skill == "coherence_and_cohesion"
    assert _reason_values(recency) == ["largest_target_gap"]
    assert recency.selection_trace.stages[-1].stage == "recent_practice"

    fallback = plan_practice_v2(
        learner_target_band=_target(),
        states=_tie_states(),
        memory_context=_context(),
    )
    assert fallback.decision.target_skill == "task_response"
    assert _reason_values(fallback) == ["largest_target_gap", "priority_tiebreak"]
    assert fallback.selection_trace.stages[-1].stage == "canonical_priority"
    assert fallback.selection_trace.stages[-1].narrowed is True


def test_selected_skill_insufficient_evidence_keeps_v1_qualifier_semantics() -> None:
    states = _states(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
        counts={"coherence_and_cohesion": 1},
    )
    result = plan_practice_v2(
        learner_target_band=_target(),
        states=states,
        memory_context=_context(persistent={"coherence_and_cohesion": True}),
    )
    assert result.decision.target_skill == "coherence_and_cohesion"
    assert _reason_values(result) == ["largest_target_gap", "insufficient_evidence"]


def test_v2_planner_is_pure_and_deterministic() -> None:
    first = plan_practice_v2(
        learner_target_band=_target(),
        states=_tie_states(),
        memory_context=_context(),
    )
    second = plan_practice_v2(
        learner_target_band=_target(),
        states=_tie_states(),
        memory_context=_context(),
    )
    assert first == second

    import app.learner.memory_planner as planner_module

    source = inspect.getsource(planner_module)
    import_lines = [
        line.strip().lower()
        for line in source.splitlines()
        if line.strip().startswith(("from ", "import "))
    ]
    for forbidden in ("sqlalchemy", "provider", "llm"):
        assert all(forbidden not in line for line in import_lines)
