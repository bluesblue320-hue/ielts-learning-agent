"""P3-08 planner-owned decision contract.

Strict Pydantic v2 schemas for the deterministic practice-planning decision.
These schemas express the accepted P3-08 policy (version
``writing-practice-gap-v1``) and contain no planner algorithm, ORM, transaction,
or LLM behavior. The production planner implementation is owned by P3-09.

The schema validates only local decision invariants: it never recomputes all
skill gaps or re-runs tie-break selection to prove that ``target_skill`` is the
largest-gap skill. That selection algorithm belongs to P3-09.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.learner.planning_policy import MIN_ESTABLISHED_EVIDENCE_COUNT
from app.learner.writing_policy import WRITING_SKILLS
from app.schemas.common import BandScore
from app.schemas.learner import (
    DerivedStateBand,
    LearnerSkillStateSet,
    WritingSkillKey,
)


class DecisionType(StrEnum):
    """The two mutually exclusive planning decision types."""

    PRACTICE = "practice"
    NO_PRACTICE = "no_practice"


class PlannerReasonCode(StrEnum):
    """The frozen planner v1 reason-code taxonomy."""

    LARGEST_TARGET_GAP = "largest_target_gap"
    PRIORITY_TIEBREAK = "priority_tiebreak"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    TARGET_ACHIEVED = "target_achieved"
    COLD_START = "cold_start"
    INCOMPLETE_STATE = "incomplete_state"
    TARGET_UNSET = "target_unset"


PlannerVersion = Literal["writing-practice-gap-v1"]

# Exact valid reason-code sequences for planner v1. Ordering is fully
# deterministic: any sequence not listed here is rejected, never reordered.
_VALID_PRACTICE_REASON_SEQUENCES = frozenset(
    {
        (PlannerReasonCode.LARGEST_TARGET_GAP,),
        (PlannerReasonCode.LARGEST_TARGET_GAP, PlannerReasonCode.PRIORITY_TIEBREAK),
        (PlannerReasonCode.LARGEST_TARGET_GAP, PlannerReasonCode.INSUFFICIENT_EVIDENCE),
        (
            PlannerReasonCode.LARGEST_TARGET_GAP,
            PlannerReasonCode.PRIORITY_TIEBREAK,
            PlannerReasonCode.INSUFFICIENT_EVIDENCE,
        ),
    }
)

_VALID_NO_PRACTICE_REASON_SEQUENCES = frozenset(
    {
        (PlannerReasonCode.TARGET_ACHIEVED,),
        (PlannerReasonCode.TARGET_ACHIEVED, PlannerReasonCode.INSUFFICIENT_EVIDENCE),
        (PlannerReasonCode.COLD_START,),
        (PlannerReasonCode.INCOMPLETE_STATE,),
        (PlannerReasonCode.TARGET_UNSET,),
    }
)


class PracticeRecommendationDecision(BaseModel):
    """The structured, auditable planner decision for one learning update.

    A valid decision is either ``practice`` with a required ``target_skill`` and
    estimate that matches the state snapshot, or ``no_practice`` with a null
    ``target_skill``. Every decision carries exactly one valid reason-code
    sequence, a full decision-time state snapshot, and the frozen planner
    version. The reason semantics must agree with the state snapshot.
    """

    model_config = ConfigDict(extra="forbid")

    decision_type: DecisionType
    target_skill: WritingSkillKey | None = None
    learner_target_band: BandScore | None = None
    current_estimate: DerivedStateBand | None = None
    reason_codes: list[PlannerReasonCode]
    planner_version: PlannerVersion
    state_snapshot: LearnerSkillStateSet

    @model_validator(mode="after")
    def _check_decision_contract(self) -> "PracticeRecommendationDecision":
        sequence = tuple(self.reason_codes)

        if self.decision_type == DecisionType.PRACTICE:
            self._check_practice(sequence)
        else:
            self._check_no_practice(sequence)
        return self

    def _check_practice(
        self, sequence: tuple[PlannerReasonCode, ...]
    ) -> None:
        if sequence not in _VALID_PRACTICE_REASON_SEQUENCES:
            raise ValueError(
                "invalid practice reason sequence: "
                f"{[code.value for code in self.reason_codes]}"
            )
        if self.target_skill is None:
            raise ValueError("practice decision requires target_skill")
        if self.learner_target_band is None:
            raise ValueError("practice decision requires learner_target_band")
        if self.current_estimate is None:
            raise ValueError("practice decision requires current_estimate")

        snapshot_state = getattr(self.state_snapshot, self.target_skill)
        if snapshot_state.estimated_band is None:
            raise ValueError(
                "practice target skill must be observed in the state snapshot"
            )
        if self.current_estimate != snapshot_state.estimated_band:
            raise ValueError(
                "current_estimate must equal the snapshot estimate for target_skill"
            )
        if self.current_estimate >= self.learner_target_band.value:
            raise ValueError("practice requires a strictly positive target gap")

        # Bidirectional evidence qualifier rule for the selected skill.
        has_insufficient = (
            PlannerReasonCode.INSUFFICIENT_EVIDENCE in self.reason_codes
        )
        low_evidence = snapshot_state.evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT
        if low_evidence and not has_insufficient:
            raise ValueError(
                "selected skill has low evidence but reason lacks "
                "insufficient_evidence"
            )
        if not low_evidence and has_insufficient:
            raise ValueError(
                "selected skill has established evidence but reason carries "
                "insufficient_evidence"
            )

    def _check_no_practice(
        self, sequence: tuple[PlannerReasonCode, ...]
    ) -> None:
        if sequence not in _VALID_NO_PRACTICE_REASON_SEQUENCES:
            raise ValueError(
                "invalid no_practice reason sequence: "
                f"{[code.value for code in self.reason_codes]}"
            )
        if self.target_skill is not None:
            raise ValueError("no_practice decision must have null target_skill")
        if self.current_estimate is not None:
            raise ValueError("no_practice decision must have null current_estimate")

        primary = self.reason_codes[0]

        if primary == PlannerReasonCode.TARGET_UNSET:
            if self.learner_target_band is not None:
                raise ValueError(
                    "target_unset decision must have null learner_target_band"
                )
            # No snapshot-shape requirement for target_unset.
            return

        if self.learner_target_band is None:
            raise ValueError(
                "no_practice decision (non target_unset) requires learner_target_band"
            )

        states = [getattr(self.state_snapshot, skill) for skill in WRITING_SKILLS]
        observed = [s for s in states if s.estimated_band is not None]

        if primary == PlannerReasonCode.TARGET_ACHIEVED:
            if len(observed) != len(states):
                raise ValueError(
                    "target_achieved requires all four skills observed"
                )
            target = self.learner_target_band.value
            for state in states:
                if state.estimated_band < target:
                    raise ValueError(
                        "target_achieved requires every skill >= target"
                    )
            low = any(
                s.evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT for s in states
            )
            has_insufficient = (
                PlannerReasonCode.INSUFFICIENT_EVIDENCE in self.reason_codes
            )
            if low and not has_insufficient:
                raise ValueError(
                    "target_achieved requires insufficient_evidence when any "
                    "skill has low evidence"
                )
            if not low and has_insufficient:
                raise ValueError(
                    "target_achieved must not carry insufficient_evidence when "
                    "all skills are established"
                )
        elif primary == PlannerReasonCode.COLD_START:
            if observed:
                raise ValueError("cold_start requires all four skills unobserved")
        elif primary == PlannerReasonCode.INCOMPLETE_STATE:
            if not observed:
                raise ValueError(
                    "incomplete_state requires at least one observed skill"
                )
            if len(observed) == len(states):
                raise ValueError(
                    "incomplete_state requires at least one unobserved skill"
                )
