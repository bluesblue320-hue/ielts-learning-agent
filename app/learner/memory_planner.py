"""Pure Phase 7 deterministic Writing planner v2.

The frozen v1 planner remains in ``app.learner.planner``. This module first
performs the same state-and-target base selection, then accepts Memory facts
only for an exact maximum-gap tie. It contains no ORM, query, provider, or LLM
behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.learner.memory_planning_policy import (
    PLANNER_V2_VERSION,
    SELECTION_TRACE_VERSION,
)
from app.learner.planning_policy import (
    MIN_ESTABLISHED_EVIDENCE_COUNT,
    PRACTICE_TIEBREAK_PRIORITY,
)
from app.learner.writing_policy import WRITING_SKILLS
from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillStateSet, WritingSkillKey
from app.schemas.planning import (
    DecisionType,
    MemoryAwarePlanningContext,
    PlannerReasonCode,
    PlannerSelectionTrace,
    PlannerSelectionTraceStage,
    PracticeRecommendationDecisionV2,
)


_ESTABLISHED_TREND_CONCERN = {
    "declining": 0,
    "stable": 1,
    "improving": 2,
}


@dataclass(frozen=True)
class PlannerV2BaseSelection:
    """Either a terminal v2 decision or the exact tie that needs Memory."""

    learner_target_band: BandScore | None
    states: LearnerSkillStateSet
    decision: PracticeRecommendationDecisionV2 | None
    exact_max_gap_candidates: tuple[WritingSkillKey, ...] = ()

    @property
    def requires_memory_context(self) -> bool:
        """Whether the base selection reached the exact-tie boundary."""

        return len(self.exact_max_gap_candidates) > 1


@dataclass(frozen=True)
class MemoryAwarePlanningResult:
    """The v2 decision plus an exact-tie-only internal selection trace."""

    decision: PracticeRecommendationDecisionV2
    selection_trace: PlannerSelectionTrace | None


def select_practice_v2_base(
    *,
    learner_target_band: BandScore | None,
    states: LearnerSkillStateSet,
) -> PlannerV2BaseSelection:
    """Apply state-first v1 branches and detect (but do not resolve) a tie."""

    skill_states = {skill: getattr(states, skill) for skill in WRITING_SKILLS}

    if learner_target_band is None:
        return _terminal(
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
        return _terminal(
            states=states,
            learner_target_band=learner_target_band,
            reason_codes=[PlannerReasonCode.COLD_START],
        )
    if len(observed) < len(skill_states):
        return _terminal(
            states=states,
            learner_target_band=learner_target_band,
            reason_codes=[PlannerReasonCode.INCOMPLETE_STATE],
        )

    target = learner_target_band.value
    if all(state.estimated_band >= target for state in skill_states.values()):
        reasons = [PlannerReasonCode.TARGET_ACHIEVED]
        if any(
            state.evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT
            for state in skill_states.values()
        ):
            reasons.append(PlannerReasonCode.INSUFFICIENT_EVIDENCE)
        return _terminal(
            states=states,
            learner_target_band=learner_target_band,
            reason_codes=reasons,
        )

    gaps = {
        skill: target - state.estimated_band
        for skill, state in skill_states.items()
    }
    maximum = max(gaps.values())
    candidates = tuple(
        skill for skill in PRACTICE_TIEBREAK_PRIORITY if gaps[skill] == maximum
    )
    if len(candidates) == 1:
        return _terminal(
            states=states,
            learner_target_band=learner_target_band,
            reason_codes=_practice_reasons(states=states, selected=candidates[0]),
            target_skill=candidates[0],
        )

    return PlannerV2BaseSelection(
        learner_target_band=learner_target_band,
        states=states,
        decision=None,
        exact_max_gap_candidates=candidates,
    )


def resolve_practice_v2_exact_tie(
    *,
    base_selection: PlannerV2BaseSelection,
    memory_context: MemoryAwarePlanningContext,
) -> MemoryAwarePlanningResult:
    """Resolve an already-detected exact tie through the frozen hierarchy."""

    if not base_selection.requires_memory_context:
        raise ValueError("memory context is permitted only for an exact maximum-gap tie")
    if base_selection.decision is not None:
        raise ValueError("terminal base selection cannot be memory-resolved")

    candidates = list(base_selection.exact_max_gap_candidates)
    stages: list[PlannerSelectionTraceStage] = []

    persistent_candidates = [
        skill
        for skill in candidates
        if getattr(memory_context.skills, skill).persistent_gap
        and getattr(memory_context.skills, skill).persistent_gap_status == "established"
    ]
    candidates, persistent_stage = _record_stage(
        stage="persistent_gap",
        before=candidates,
        proposed=persistent_candidates,
    )
    stages.append(persistent_stage)

    if len(candidates) > 1:
        contexts = [getattr(memory_context.skills, skill) for skill in candidates]
        if all(context.trend in _ESTABLISHED_TREND_CONCERN for context in contexts):
            best = min(_ESTABLISHED_TREND_CONCERN[context.trend] for context in contexts)
            trend_candidates = [
                skill
                for skill in candidates
                if _ESTABLISHED_TREND_CONCERN[
                    getattr(memory_context.skills, skill).trend
                ]
                == best
            ]
        else:
            trend_candidates = list(candidates)
        candidates, trend_stage = _record_stage(
            stage="trend",
            before=candidates,
            proposed=trend_candidates,
        )
        stages.append(trend_stage)

    if len(candidates) > 1:
        minimum = min(
            getattr(memory_context.skills, skill).recent_practice_count
            for skill in candidates
        )
        recent_candidates = [
            skill
            for skill in candidates
            if getattr(memory_context.skills, skill).recent_practice_count == minimum
        ]
        candidates, recent_stage = _record_stage(
            stage="recent_practice",
            before=candidates,
            proposed=recent_candidates,
        )
        stages.append(recent_stage)

    used_canonical_priority = False
    if len(candidates) > 1:
        canonical_candidates = [candidates[0]]
        candidates, priority_stage = _record_stage(
            stage="canonical_priority",
            before=candidates,
            proposed=canonical_candidates,
        )
        stages.append(priority_stage)
        used_canonical_priority = priority_stage.narrowed

    selected = candidates[0]
    trace = PlannerSelectionTrace(
        trace_version=SELECTION_TRACE_VERSION,
        initial_max_gap_candidates=list(base_selection.exact_max_gap_candidates),
        stages=stages,
        selected_skill=selected,
    )
    decision = _practice_decision(
        states=base_selection.states,
        learner_target_band=base_selection.learner_target_band,
        selected=selected,
        used_canonical_priority=used_canonical_priority,
    )
    return MemoryAwarePlanningResult(decision=decision, selection_trace=trace)


def plan_practice_v2(
    *,
    learner_target_band: BandScore | None,
    states: LearnerSkillStateSet,
    memory_context: MemoryAwarePlanningContext | None = None,
) -> MemoryAwarePlanningResult:
    """Return a v2 decision, requiring Memory only for the exact-tie branch."""

    base_selection = select_practice_v2_base(
        learner_target_band=learner_target_band,
        states=states,
    )
    if not base_selection.requires_memory_context:
        if memory_context is not None:
            raise ValueError("terminal v2 decisions must not receive memory context")
        assert base_selection.decision is not None
        return MemoryAwarePlanningResult(
            decision=base_selection.decision,
            selection_trace=None,
        )
    if memory_context is None:
        raise ValueError("exact maximum-gap ties require memory context")
    return resolve_practice_v2_exact_tie(
        base_selection=base_selection,
        memory_context=memory_context,
    )


def _record_stage(
    *,
    stage: str,
    before: list[WritingSkillKey],
    proposed: list[WritingSkillKey],
) -> tuple[list[WritingSkillKey], PlannerSelectionTraceStage]:
    """Record a stage without allowing an empty/non-narrowing filter through."""

    after = list(proposed) if 0 < len(proposed) < len(before) else list(before)
    return after, PlannerSelectionTraceStage(
        stage=stage,
        candidates_before=list(before),
        candidates_after=after,
        narrowed=after != before,
    )


def _terminal(
    *,
    states: LearnerSkillStateSet,
    learner_target_band: BandScore | None,
    reason_codes: list[PlannerReasonCode],
    target_skill: WritingSkillKey | None = None,
) -> PlannerV2BaseSelection:
    """Create a validated v2 terminal decision with no Memory boundary."""

    if target_skill is None:
        decision = PracticeRecommendationDecisionV2(
            decision_type=DecisionType.NO_PRACTICE,
            target_skill=None,
            learner_target_band=learner_target_band,
            current_estimate=None,
            reason_codes=reason_codes,
            planner_version=PLANNER_V2_VERSION,
            state_snapshot=states,
        )
    else:
        decision = _practice_decision(
            states=states,
            learner_target_band=learner_target_band,
            selected=target_skill,
            used_canonical_priority=False,
        )
    return PlannerV2BaseSelection(
        learner_target_band=learner_target_band,
        states=states,
        decision=decision,
    )


def _practice_reasons(
    *,
    states: LearnerSkillStateSet,
    selected: WritingSkillKey,
    used_canonical_priority: bool = False,
) -> list[PlannerReasonCode]:
    """Keep the frozen v1 reason-code taxonomy and selected-skill qualifier."""

    reasons = [PlannerReasonCode.LARGEST_TARGET_GAP]
    if used_canonical_priority:
        reasons.append(PlannerReasonCode.PRIORITY_TIEBREAK)
    if getattr(states, selected).evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT:
        reasons.append(PlannerReasonCode.INSUFFICIENT_EVIDENCE)
    return reasons


def _practice_decision(
    *,
    states: LearnerSkillStateSet,
    learner_target_band: BandScore | None,
    selected: WritingSkillKey,
    used_canonical_priority: bool,
) -> PracticeRecommendationDecisionV2:
    """Build a validated normal-practice v2 decision."""

    assert learner_target_band is not None
    state = getattr(states, selected)
    return PracticeRecommendationDecisionV2(
        decision_type=DecisionType.PRACTICE,
        target_skill=selected,
        learner_target_band=learner_target_band,
        current_estimate=state.estimated_band,
        reason_codes=_practice_reasons(
            states=states,
            selected=selected,
            used_canonical_priority=used_canonical_priority,
        ),
        planner_version=PLANNER_V2_VERSION,
        state_snapshot=states,
    )
