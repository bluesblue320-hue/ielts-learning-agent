"""Focused tests for the P3-09 deterministic practice planner.

The planner implements the frozen P3-08 policy exactly; every decision it
produces must pass the P3-08 decision-contract schema validation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.learner.planner import plan_practice
from app.learner.writing_policy import WRITING_SKILLS
from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillState, LearnerSkillStateSet
from app.schemas.planning import DecisionType, PlannerReasonCode

DT = datetime(2026, 1, 1, 12, 0, 0)


def _state(skill: str, band: str | None, count: int) -> LearnerSkillState:
    observed = band is not None
    return LearnerSkillState(
        learner_id=1,
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
) -> LearnerSkillStateSet:
    counts = counts or {}
    return LearnerSkillStateSet(
        task_response=_state("task_response", bands["task_response"], counts.get("task_response", 3)),
        coherence_and_cohesion=_state(
            "coherence_and_cohesion", bands["coherence_and_cohesion"], counts.get("coherence_and_cohesion", 3)
        ),
        lexical_resource=_state("lexical_resource", bands["lexical_resource"], counts.get("lexical_resource", 3)),
        grammatical_range_and_accuracy=_state(
            "grammatical_range_and_accuracy",
            bands["grammatical_range_and_accuracy"],
            counts.get("grammatical_range_and_accuracy", 3),
        ),
    )


def decide(bands: dict[str, str | None], counts: dict[str, int] | None = None, target: str = "7.0"):
    return plan_practice(
        learner_target_band=BandScore(value=Decimal(target)),
        states=build_states(bands, counts),
    )


def reasons(decision) -> list[str]:
    return [code.value for code in decision.reason_codes]


# ---------------------------------------------------------------------------
# Required P3-08 policy examples
# ---------------------------------------------------------------------------


def test_a_single_largest_gap() -> None:
    decision = decide(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.75",
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    assert decision.decision_type == DecisionType.PRACTICE
    assert decision.target_skill == "task_response"
    assert reasons(decision) == ["largest_target_gap"]


def test_b_equal_maximum_gap_tie() -> None:
    decision = decide(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    assert decision.decision_type == DecisionType.PRACTICE
    assert decision.target_skill == "task_response"
    assert reasons(decision) == ["largest_target_gap", "priority_tiebreak"]


def test_c_insufficient_evidence_but_recommendation_possible() -> None:
    decision = decide(
        {
            "task_response": "5.5",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.0",
        },
        counts={s: 1 for s in WRITING_SKILLS},
    )
    assert decision.decision_type == DecisionType.PRACTICE
    assert decision.target_skill == "task_response"
    assert reasons(decision) == ["largest_target_gap", "insufficient_evidence"]


def test_d_target_achieved() -> None:
    decision = decide(
        {
            "task_response": "7.0",
            "coherence_and_cohesion": "7.25",
            "lexical_resource": "7.0",
            "grammatical_range_and_accuracy": "7.0",
        }
    )
    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert decision.target_skill is None
    assert reasons(decision) == ["target_achieved"]


def test_e_target_achieved_but_insufficient_evidence() -> None:
    decision = decide(
        {
            "task_response": "7.0",
            "coherence_and_cohesion": "7.25",
            "lexical_resource": "7.0",
            "grammatical_range_and_accuracy": "7.0",
        },
        counts={s: 1 for s in WRITING_SKILLS},
    )
    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert reasons(decision) == ["target_achieved", "insufficient_evidence"]


def test_f_cold_start() -> None:
    decision = decide(
        {
            "task_response": None,
            "coherence_and_cohesion": None,
            "lexical_resource": None,
            "grammatical_range_and_accuracy": None,
        }
    )
    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert decision.target_skill is None
    assert reasons(decision) == ["cold_start"]


def test_g_incomplete_state() -> None:
    decision = decide(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": None,
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert reasons(decision) == ["incomplete_state"]


def test_h_target_unset() -> None:
    states = build_states(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    decision = plan_practice(learner_target_band=None, states=states)
    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert decision.target_skill is None
    assert decision.learner_target_band is None
    assert reasons(decision) == ["target_unset"]


def test_j_boundary_target_equality() -> None:
    decision = decide(
        {
            "task_response": "6.50",
            "coherence_and_cohesion": "6.50",
            "lexical_resource": "6.50",
            "grammatical_range_and_accuracy": "6.50",
        },
        target="6.5",
    )
    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert reasons(decision) == ["target_achieved"]


def test_k_one_skill_below_target_by_0_01() -> None:
    decision = decide(
        {
            "task_response": "6.49",
            "coherence_and_cohesion": "6.50",
            "lexical_resource": "6.50",
            "grammatical_range_and_accuracy": "6.50",
        },
        target="6.5",
    )
    assert decision.decision_type == DecisionType.PRACTICE
    assert decision.target_skill == "task_response"
    assert reasons(decision) == ["largest_target_gap"]


# ---------------------------------------------------------------------------
# Tie behavior beyond the required example
# ---------------------------------------------------------------------------


def test_tie_break_priority_order_is_frozen() -> None:
    # All four skills at the same estimate -> all four share the max gap.
    decision = decide(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.0",
            "grammatical_range_and_accuracy": "6.0",
        }
    )
    assert decision.target_skill == "task_response"
    assert reasons(decision) == ["largest_target_gap", "priority_tiebreak"]

    # Two-way tie that excludes task_response must resolve by priority.
    decision = decide(
        {
            "task_response": "6.5",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.0",
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    assert decision.target_skill == "coherence_and_cohesion"
    assert reasons(decision) == ["largest_target_gap", "priority_tiebreak"]


def test_insufficient_evidence_qualifier_reflects_selected_skill() -> None:
    # Selected skill (task_response) has count 2; others count 3.
    decision = decide(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
        counts={"task_response": 2},
    )
    assert decision.target_skill == "task_response"
    assert reasons(decision) == ["largest_target_gap", "insufficient_evidence"]

    # Selected skill established; another skill low evidence is irrelevant.
    decision = decide(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
        counts={"coherence_and_cohesion": 1},
    )
    assert decision.target_skill == "task_response"
    assert reasons(decision) == ["largest_target_gap"]


# ---------------------------------------------------------------------------
# Determinism / input-order independence / snapshot integrity
# ---------------------------------------------------------------------------


def test_deterministic_repeated_runs() -> None:
    states = build_states(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    target = BandScore(value=Decimal("7.0"))
    first = plan_practice(learner_target_band=target, states=states)
    second = plan_practice(learner_target_band=target, states=states)
    assert first == second


def test_planner_iterates_canonical_skill_order() -> None:
    # The planner must be independent of input dictionary ordering because it
    # reads the state set by canonical field access only.
    states = build_states(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.0",
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    decision = plan_practice(
        learner_target_band=BandScore(value=Decimal("7.0")),
        states=states,
    )
    # Max gap shared by TR/CC/LR -> frozen priority picks task_response.
    assert decision.target_skill == "task_response"
    assert decision.state_snapshot == states


def test_practice_decision_snapshot_is_decision_time_state() -> None:
    decision = decide(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    )
    snapshot = decision.state_snapshot
    assert getattr(snapshot, decision.target_skill).estimated_band == Decimal("6.0")
    assert decision.current_estimate == Decimal("6.0")
    assert decision.learner_target_band.value == Decimal("7.0")


def test_no_practice_decision_still_carries_complete_snapshot() -> None:
    states = build_states(
        {
            "task_response": "7.0",
            "coherence_and_cohesion": "7.25",
            "lexical_resource": "7.0",
            "grammatical_range_and_accuracy": "7.0",
        }
    )
    decision = plan_practice(
        learner_target_band=BandScore(value=Decimal("7.0")),
        states=states,
    )
    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert decision.state_snapshot == states
    assert [getattr(decision.state_snapshot, s).evidence_count for s in WRITING_SKILLS] == [3, 3, 3, 3]
