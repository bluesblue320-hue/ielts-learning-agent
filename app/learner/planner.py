"""Deterministic Writing practice planner (P3-09).

Implements exactly the frozen P3-08 policy (``writing-practice-gap-v1``): the
planner decides only WHAT Writing skill should be practiced next, or
deterministically records that no evidence-based practice target is required
(``no_practice``). It never generates lessons, exercises, or study content.

The planner is pure and deterministic: the same learner target and state
snapshot always produce the same single decision, independent of input
collection order. No LLM, no provider, no persistence orchestration.
"""

from __future__ import annotations

from decimal import Decimal

from app.learner.planning_policy import (
    MIN_ESTABLISHED_EVIDENCE_COUNT,
    PLANNER_VERSION,
    PRACTICE_TIEBREAK_PRIORITY,
)
from app.learner.writing_policy import WRITING_SKILLS
from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillStateSet, WritingSkillKey
from app.schemas.planning import (
    DecisionType,
    PlannerReasonCode,
    PracticeRecommendationDecision,
)


def plan_practice(
    *,
    learner_target_band: BandScore | None,
    states: LearnerSkillStateSet,
) -> PracticeRecommendationDecision:
    """Return exactly one deterministic planning decision.

    The returned decision carries the complete decision-time state snapshot so
    the outcome is auditable. All branch behavior follows the frozen P3-08
    policy: ``target_unset``, ``cold_start``, ``incomplete_state``,
    ``target_achieved``, and largest-positive-gap ``practice`` with the frozen
    tie-break priority.
    """

    skill_states = {skill: getattr(states, skill) for skill in WRITING_SKILLS}

    if learner_target_band is None:
        return _no_practice(
            states=states,
            learner_target_band=None,
            reason_codes=[PlannerReasonCode.TARGET_UNSET],
        )

    observed = {
        skill: state
        for skill, state in skill_states.items()
        if state.estimated_band is not None
    }

    if not observed:
        return _no_practice(
            states=states,
            learner_target_band=learner_target_band,
            reason_codes=[PlannerReasonCode.COLD_START],
        )

    if len(observed) < len(skill_states):
        return _no_practice(
            states=states,
            learner_target_band=learner_target_band,
            reason_codes=[PlannerReasonCode.INCOMPLETE_STATE],
        )

    target = learner_target_band.value
    if all(state.estimated_band >= target for state in skill_states.values()):
        reason_codes = [PlannerReasonCode.TARGET_ACHIEVED]
        if any(
            state.evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT
            for state in skill_states.values()
        ):
            reason_codes.append(PlannerReasonCode.INSUFFICIENT_EVIDENCE)
        return _no_practice(
            states=states,
            learner_target_band=learner_target_band,
            reason_codes=reason_codes,
        )

    gaps = {
        skill: target - state.estimated_band
        for skill, state in skill_states.items()
    }
    max_gap = max(gaps.values())
    candidates = [skill for skill, gap in gaps.items() if gap == max_gap]
    used_tiebreak = len(candidates) > 1
    selected = next(
        skill for skill in PRACTICE_TIEBREAK_PRIORITY if skill in candidates
    )
    selected_state = skill_states[selected]

    reason_codes: list[PlannerReasonCode] = [
        PlannerReasonCode.LARGEST_TARGET_GAP
    ]
    if used_tiebreak:
        reason_codes.append(PlannerReasonCode.PRIORITY_TIEBREAK)
    if selected_state.evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT:
        reason_codes.append(PlannerReasonCode.INSUFFICIENT_EVIDENCE)

    return PracticeRecommendationDecision(
        decision_type=DecisionType.PRACTICE,
        target_skill=selected,
        learner_target_band=learner_target_band,
        current_estimate=selected_state.estimated_band,
        reason_codes=reason_codes,
        planner_version=PLANNER_VERSION,
        state_snapshot=states,
    )


def _no_practice(
    *,
    states: LearnerSkillStateSet,
    learner_target_band: BandScore | None,
    reason_codes: list[PlannerReasonCode],
) -> PracticeRecommendationDecision:
    """Build a validated no_practice decision with a null target."""
    return PracticeRecommendationDecision(
        decision_type=DecisionType.NO_PRACTICE,
        target_skill=None,
        learner_target_band=learner_target_band,
        current_estimate=None,
        reason_codes=reason_codes,
        planner_version=PLANNER_VERSION,
        state_snapshot=states,
    )
