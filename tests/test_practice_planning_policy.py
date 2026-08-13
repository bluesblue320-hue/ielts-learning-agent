"""P3-08 boundary and example tests for the frozen practice planning policy.

These tests encode the accepted P3-08 decisions using a test-local reference
decision function. They import no production planner algorithm, ORM,
transaction, service, or LLM code. The production planner belongs to P3-09.

The reference function reproduces the frozen policy so the tests prove the
normative contract without implementing the production planner.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from decimal import Decimal
from typing import get_args

import pytest
from pydantic import ValidationError

from app.learner import planning_policy as pp
from app.learner.writing_policy import WRITING_SKILLS
from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillState, LearnerSkillStateSet
from app.schemas.planning import (
    DecisionType,
    PlannerReasonCode,
    PlannerVersion,
    PracticeRecommendationDecision,
)

DT = datetime(2026, 1, 1, 12, 0, 0)


# ---------------------------------------------------------------------------
# Test-local helpers
# ---------------------------------------------------------------------------


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


def _no_practice(
    states: LearnerSkillStateSet,
    reasons: list[PlannerReasonCode],
    target: Decimal,
) -> PracticeRecommendationDecision:
    return PracticeRecommendationDecision(
        decision_type=DecisionType.NO_PRACTICE,
        target_skill=None,
        learner_target_band=BandScore(value=target),
        current_estimate=None,
        reason_codes=reasons,
        planner_version=pp.PLANNER_VERSION,
        state_snapshot=states,
    )


def reference_decide(
    target: Decimal | None,
    states: LearnerSkillStateSet,
) -> PracticeRecommendationDecision:
    """Test-local reference planner reproducing the frozen P3-08 policy."""

    if target is None:
        return PracticeRecommendationDecision(
            decision_type=DecisionType.NO_PRACTICE,
            target_skill=None,
            learner_target_band=None,
            current_estimate=None,
            reason_codes=[PlannerReasonCode.TARGET_UNSET],
            planner_version=pp.PLANNER_VERSION,
            state_snapshot=states,
        )

    observed = {skill: getattr(states, skill) for skill in WRITING_SKILLS}
    unobserved = [
        skill for skill in WRITING_SKILLS if observed[skill].estimated_band is None
    ]

    if len(unobserved) == len(WRITING_SKILLS):
        return _no_practice(states, [PlannerReasonCode.COLD_START], target)

    if unobserved:
        return _no_practice(states, [PlannerReasonCode.INCOMPLETE_STATE], target)

    gaps = {
        skill: target - observed[skill].estimated_band for skill in WRITING_SKILLS
    }
    max_gap = max(gaps.values())

    if max_gap <= 0:
        reasons = [PlannerReasonCode.TARGET_ACHIEVED]
        if any(
            observed[skill].evidence_count < pp.MIN_ESTABLISHED_EVIDENCE_COUNT
            for skill in WRITING_SKILLS
        ):
            reasons.append(PlannerReasonCode.INSUFFICIENT_EVIDENCE)
        return _no_practice(states, reasons, target)

    candidates = [
        skill
        for skill in pp.PRACTICE_TIEBREAK_PRIORITY
        if gaps[skill] == max_gap
    ]
    selected = candidates[0]
    tied = len(candidates) > 1

    reasons = [PlannerReasonCode.LARGEST_TARGET_GAP]
    if tied:
        reasons.append(PlannerReasonCode.PRIORITY_TIEBREAK)
    if observed[selected].evidence_count < pp.MIN_ESTABLISHED_EVIDENCE_COUNT:
        reasons.append(PlannerReasonCode.INSUFFICIENT_EVIDENCE)

    return PracticeRecommendationDecision(
        decision_type=DecisionType.PRACTICE,
        target_skill=selected,
        learner_target_band=BandScore(value=target),
        current_estimate=observed[selected].estimated_band,
        reason_codes=reasons,
        planner_version=pp.PLANNER_VERSION,
        state_snapshot=states,
    )


def _snapshot_dump() -> dict:
    # Internally consistent with the default practice decision:
    # target_skill=task_response, current_estimate=6.0, target=7.0.
    return build_states(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    ).model_dump()


def _decision(**overrides: object) -> PracticeRecommendationDecision:
    payload: dict[str, object] = {
        "decision_type": "practice",
        "target_skill": "task_response",
        "learner_target_band": {"value": "7.0"},
        "current_estimate": "6.0",
        "reason_codes": ["largest_target_gap"],
        "planner_version": "writing-practice-gap-v1",
        "state_snapshot": _snapshot_dump(),
    }
    payload.update(overrides)
    return PracticeRecommendationDecision.model_validate(payload)


# ---------------------------------------------------------------------------
# Constants and taxonomy
# ---------------------------------------------------------------------------


def test_planner_version_is_frozen() -> None:
    assert pp.PLANNER_VERSION == "writing-practice-gap-v1"
    assert get_args(PlannerVersion) == ("writing-practice-gap-v1",)


def test_evidence_threshold_is_three() -> None:
    assert pp.MIN_ESTABLISHED_EVIDENCE_COUNT == 3


def test_tiebreak_priority_is_independently_frozen() -> None:
    # Planner priority is frozen explicitly, not derived from WRITING_SKILLS
    # (whose tuple order is presentation-only per P3-02).
    assert pp.PRACTICE_TIEBREAK_PRIORITY == (
        "task_response",
        "coherence_and_cohesion",
        "lexical_resource",
        "grammatical_range_and_accuracy",
    )


def test_tiebreak_priority_contains_exactly_canonical_skills() -> None:
    assert set(pp.PRACTICE_TIEBREAK_PRIORITY) == set(WRITING_SKILLS)


def test_reason_code_taxonomy_is_exact() -> None:
    assert {code.value for code in PlannerReasonCode} == {
        "largest_target_gap",
        "priority_tiebreak",
        "insufficient_evidence",
        "target_achieved",
        "cold_start",
        "incomplete_state",
        "target_unset",
    }


def test_decision_types_are_exact() -> None:
    assert {d.value for d in DecisionType} == {"practice", "no_practice"}


# ---------------------------------------------------------------------------
# Decision contract validation
# ---------------------------------------------------------------------------


def test_practice_requires_target_skill() -> None:
    with pytest.raises(ValidationError, match="target_skill"):
        _decision(target_skill=None)


def test_practice_requires_learner_target_band() -> None:
    with pytest.raises(ValidationError, match="learner_target_band"):
        _decision(learner_target_band=None)


def test_practice_requires_current_estimate() -> None:
    with pytest.raises(ValidationError, match="current_estimate"):
        _decision(current_estimate=None)


def test_practice_requires_largest_target_gap() -> None:
    with pytest.raises(ValidationError):
        _decision(reason_codes=["cold_start"])


def test_no_practice_forbids_target_skill() -> None:
    with pytest.raises(ValidationError, match="target_skill"):
        _decision(
            decision_type="no_practice",
            target_skill="task_response",
            current_estimate=None,
            reason_codes=["target_achieved"],
        )


def test_no_practice_forbids_current_estimate() -> None:
    with pytest.raises(ValidationError, match="current_estimate"):
        _decision(
            decision_type="no_practice",
            target_skill=None,
            current_estimate="6.0",
            reason_codes=["target_achieved"],
        )


def test_target_unset_requires_null_target_band() -> None:
    with pytest.raises(ValidationError, match="learner_target_band"):
        _decision(
            decision_type="no_practice",
            target_skill=None,
            current_estimate=None,
            learner_target_band={"value": "7.0"},
            reason_codes=["target_unset"],
        )


def test_target_unset_accepts_null_target_band() -> None:
    decision = _decision(
        decision_type="no_practice",
        target_skill=None,
        current_estimate=None,
        learner_target_band=None,
        reason_codes=["target_unset"],
    )
    assert decision.learner_target_band is None
    assert decision.target_skill is None


def test_no_practice_requires_target_band_unless_unset() -> None:
    with pytest.raises(ValidationError, match="learner_target_band"):
        _decision(
            decision_type="no_practice",
            target_skill=None,
            current_estimate=None,
            learner_target_band=None,
            reason_codes=["target_achieved"],
        )


def _practice_snapshot(tr_band: str) -> dict:
    return build_states(
        {
            "task_response": tr_band,
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    ).model_dump()


def test_no_practice_cannot_use_largest_target_gap() -> None:
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(
            decision_type="no_practice",
            target_skill=None,
            current_estimate=None,
            reason_codes=["largest_target_gap"],
        )


def test_invalid_qualifier_order_rejected() -> None:
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(
            reason_codes=[
                "largest_target_gap",
                "insufficient_evidence",
                "priority_tiebreak",
            ]
        )


def test_empty_reason_codes_rejected() -> None:
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(reason_codes=[])


def test_multiple_primary_reasons_rejected() -> None:
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(reason_codes=["largest_target_gap", "target_achieved"])


def test_no_primary_reason_rejected() -> None:
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(reason_codes=["priority_tiebreak"])


def test_duplicate_reason_code_rejected() -> None:
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(reason_codes=["largest_target_gap", "largest_target_gap"])


def test_primary_must_come_first() -> None:
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(reason_codes=["insufficient_evidence", "largest_target_gap"])


def test_practice_estimate_must_match_snapshot() -> None:
    # Default snapshot has task_response = 6.0, so 6.5 mismatches.
    with pytest.raises(ValidationError, match="snapshot"):
        _decision(current_estimate="6.5")


def test_practice_target_skill_must_be_observed() -> None:
    unobserved = build_states(
        {
            "task_response": None,
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        }
    ).model_dump()
    with pytest.raises(ValidationError, match="observed"):
        _decision(state_snapshot=unobserved)


def test_practice_estimate_must_be_below_target() -> None:
    with pytest.raises(ValidationError, match="gap"):
        _decision(current_estimate="7.0", state_snapshot=_practice_snapshot("7.0"))
    with pytest.raises(ValidationError, match="gap"):
        _decision(current_estimate="7.5", state_snapshot=_practice_snapshot("7.5"))


def test_invalid_qualifier_combinations_rejected() -> None:
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(
            decision_type="no_practice",
            target_skill=None,
            current_estimate=None,
            reason_codes=["target_achieved", "priority_tiebreak"],
        )
    with pytest.raises(ValidationError, match="reason sequence"):
        _decision(
            decision_type="no_practice",
            target_skill=None,
            current_estimate=None,
            reason_codes=["cold_start", "insufficient_evidence"],
        )


@pytest.mark.parametrize(
    "reason_codes",
    [
        ["largest_target_gap"],
        ["largest_target_gap", "priority_tiebreak"],
        ["largest_target_gap", "insufficient_evidence"],
        ["largest_target_gap", "priority_tiebreak", "insufficient_evidence"],
    ],
)
def test_valid_practice_reason_sequences_accepted(reason_codes: list[str]) -> None:
    decision = _decision(reason_codes=reason_codes)
    assert decision.decision_type == DecisionType.PRACTICE
    assert [r.value for r in decision.reason_codes] == reason_codes


@pytest.mark.parametrize(
    "reason_codes",
    [
        ["target_achieved"],
        ["target_achieved", "insufficient_evidence"],
        ["cold_start"],
        ["incomplete_state"],
        ["target_unset"],
    ],
)
def test_valid_no_practice_reason_sequences_accepted(reason_codes: list[str]) -> None:
    target_band = None if reason_codes == ["target_unset"] else {"value": "7.0"}
    decision = _decision(
        decision_type="no_practice",
        target_skill=None,
        current_estimate=None,
        learner_target_band=target_band,
        reason_codes=reason_codes,
    )
    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert [r.value for r in decision.reason_codes] == reason_codes


def test_planner_version_must_match() -> None:
    with pytest.raises(ValidationError):
        _decision(planner_version="other-planner-v1")


def test_decision_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _decision(extra="nope")


# ---------------------------------------------------------------------------
# Required policy examples
# ---------------------------------------------------------------------------

ONE_COUNT = {skill: 1 for skill in WRITING_SKILLS}


@pytest.mark.parametrize(
    ("target", "bands", "counts", "expected_type", "expected_skill", "expected_reasons"),
    [
        # A. single largest gap
        (
            "7.0",
            {"task_response": "6.0", "coherence_and_cohesion": "6.5", "lexical_resource": "6.75", "grammatical_range_and_accuracy": "6.5"},
            None,
            "practice",
            "task_response",
            ["largest_target_gap"],
        ),
        # B. equal maximum gap tie
        (
            "7.0",
            {"task_response": "6.0", "coherence_and_cohesion": "6.0", "lexical_resource": "6.5", "grammatical_range_and_accuracy": "6.5"},
            None,
            "practice",
            "task_response",
            ["largest_target_gap", "priority_tiebreak"],
        ),
        # C. insufficient evidence but recommendation possible
        (
            "7.0",
            {"task_response": "5.5", "coherence_and_cohesion": "6.0", "lexical_resource": "6.5", "grammatical_range_and_accuracy": "6.0"},
            ONE_COUNT,
            "practice",
            "task_response",
            ["largest_target_gap", "insufficient_evidence"],
        ),
        # D. target achieved (established evidence)
        (
            "7.0",
            {"task_response": "7.0", "coherence_and_cohesion": "7.25", "lexical_resource": "7.0", "grammatical_range_and_accuracy": "7.0"},
            None,
            "no_practice",
            None,
            ["target_achieved"],
        ),
        # E. target achieved but insufficient evidence
        (
            "7.0",
            {"task_response": "7.0", "coherence_and_cohesion": "7.25", "lexical_resource": "7.0", "grammatical_range_and_accuracy": "7.0"},
            ONE_COUNT,
            "no_practice",
            None,
            ["target_achieved", "insufficient_evidence"],
        ),
        # J. boundary target equality
        (
            "6.5",
            {"task_response": "6.50", "coherence_and_cohesion": "6.50", "lexical_resource": "6.50", "grammatical_range_and_accuracy": "6.50"},
            None,
            "no_practice",
            None,
            ["target_achieved"],
        ),
        # K. one skill below target by 0.01
        (
            "6.5",
            {"task_response": "6.49", "coherence_and_cohesion": "6.50", "lexical_resource": "6.50", "grammatical_range_and_accuracy": "6.50"},
            None,
            "practice",
            "task_response",
            ["largest_target_gap"],
        ),
    ],
)
def test_required_examples(
    target: str,
    bands: dict[str, str],
    counts: dict[str, int] | None,
    expected_type: str,
    expected_skill: str | None,
    expected_reasons: list[str],
) -> None:
    states = build_states(bands, counts)
    decision = reference_decide(Decimal(target), states)

    assert decision.decision_type.value == expected_type
    assert decision.target_skill == expected_skill
    assert [r.value for r in decision.reason_codes] == expected_reasons
    assert decision.planner_version == pp.PLANNER_VERSION


def test_example_f_cold_start() -> None:
    states = build_states({skill: None for skill in WRITING_SKILLS})
    decision = reference_decide(Decimal("7.0"), states)

    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert decision.target_skill is None
    assert decision.current_estimate is None
    assert [r.value for r in decision.reason_codes] == ["cold_start"]


def test_example_g_incomplete_state() -> None:
    states = build_states(
        {
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": None,
            "grammatical_range_and_accuracy": "6.0",
        }
    )
    decision = reference_decide(Decimal("7.0"), states)

    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert decision.target_skill is None
    assert [r.value for r in decision.reason_codes] == ["incomplete_state"]


def test_example_h_target_unset() -> None:
    states = build_states({skill: "6.5" for skill in WRITING_SKILLS})
    decision = reference_decide(None, states)

    assert decision.decision_type == DecisionType.NO_PRACTICE
    assert decision.target_skill is None
    assert decision.learner_target_band is None
    assert decision.current_estimate is None
    assert [r.value for r in decision.reason_codes] == ["target_unset"]


def test_example_i_input_order_independence() -> None:
    bands = {
        "task_response": "6.0",
        "coherence_and_cohesion": "6.5",
        "lexical_resource": "6.75",
        "grammatical_range_and_accuracy": "6.5",
    }
    dump = build_states(bands).model_dump()
    forward = LearnerSkillStateSet.model_validate(
        {skill: dump[skill] for skill in WRITING_SKILLS}
    )
    reverse = LearnerSkillStateSet.model_validate(
        {skill: dump[skill] for skill in reversed(WRITING_SKILLS)}
    )

    a = reference_decide(Decimal("7.0"), forward)
    b = reference_decide(Decimal("7.0"), reverse)

    assert a.model_dump() == b.model_dump()


# ---------------------------------------------------------------------------
# State snapshot and serialization
# ---------------------------------------------------------------------------


def test_state_snapshot_is_complete() -> None:
    bands = {
        "task_response": "6.0",
        "coherence_and_cohesion": "6.5",
        "lexical_resource": "6.75",
        "grammatical_range_and_accuracy": "6.5",
    }
    decision = reference_decide(Decimal("7.0"), build_states(bands))

    for skill in WRITING_SKILLS:
        item = getattr(decision.state_snapshot, skill)
        assert item.skill == skill
        assert item.learner_id == 1
        assert item.estimated_band is not None
        assert item.state_policy_version == "writing-state-ewma-v1"
        assert item.revision >= 1
        assert item.last_evidence_id is not None


def test_decision_serializes_safely() -> None:
    bands = {
        "task_response": "6.0",
        "coherence_and_cohesion": "6.5",
        "lexical_resource": "6.75",
        "grammatical_range_and_accuracy": "6.5",
    }
    decision = reference_decide(Decimal("7.0"), build_states(bands))

    dumped = decision.model_dump()
    assert dumped["decision_type"] == "practice"
    assert dumped["target_skill"] == "task_response"
    assert dumped["planner_version"] == "writing-practice-gap-v1"
    assert dumped["reason_codes"] == ["largest_target_gap"]

    as_json = decision.model_dump_json()
    assert '"decision_type":"practice"' in as_json
    assert '"target_skill":"task_response"' in as_json
    assert '"largest_target_gap"' in as_json
    assert '"planner_version":"writing-practice-gap-v1"' in as_json


# ---------------------------------------------------------------------------
# No implementation leakage / no LLM dependency
# ---------------------------------------------------------------------------


def test_no_planner_algorithm_implementation() -> None:
    import app.learner.planning_policy as policy_module
    import app.schemas.planning as schema_module

    for module in (policy_module, schema_module):
        for forbidden in ("plan_practice", "select_skill", "compute_recommendation"):
            assert not hasattr(module, forbidden), (
                f"{module.__name__} must not implement {forbidden}"
            )


def test_no_llm_dependency() -> None:
    import app.learner.planning_policy as policy_module
    import app.schemas.planning as schema_module

    for module in (policy_module, schema_module):
        source = inspect.getsource(module)
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "llm" not in stripped.lower(), (
                    f"{module.__name__} imports an LLM module: {stripped}"
                )
