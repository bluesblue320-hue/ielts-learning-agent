"""P3-08 planner-owned decision contract.

Strict Pydantic v2 schemas for the deterministic practice-planning decision.
These schemas express the accepted P3-08 policy (version
``writing-practice-gap-v1``) and contain no planner algorithm, ORM, transaction,
or LLM behavior. The production planner implementation is owned by P3-09.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

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

# The primary reason codes: exactly one must be present, and it must be first.
_PRIMARY_REASON_CODES = frozenset(
    {
        PlannerReasonCode.LARGEST_TARGET_GAP,
        PlannerReasonCode.TARGET_ACHIEVED,
        PlannerReasonCode.COLD_START,
        PlannerReasonCode.INCOMPLETE_STATE,
        PlannerReasonCode.TARGET_UNSET,
    }
)

# Qualifiers and the primary reason codes they may accompany.
_QUALIFIER_VALID_PRIMARY = {
    PlannerReasonCode.PRIORITY_TIEBREAK: frozenset(
        {PlannerReasonCode.LARGEST_TARGET_GAP}
    ),
    PlannerReasonCode.INSUFFICIENT_EVIDENCE: frozenset(
        {
            PlannerReasonCode.LARGEST_TARGET_GAP,
            PlannerReasonCode.TARGET_ACHIEVED,
        }
    ),
}


class PracticeRecommendationDecision(BaseModel):
    """The structured, auditable planner decision for one learning update.

    A valid decision is either ``practice`` with a required ``target_skill`` and
    estimate, or ``no_practice`` with a null ``target_skill``. It always carries
    exactly one primary reason, a full decision-time state snapshot, and the
    frozen planner version.
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
        reasons = self.reason_codes

        if len(set(reasons)) != len(reasons):
            raise ValueError("reason codes must not contain duplicates")

        primaries = [code for code in reasons if code in _PRIMARY_REASON_CODES]
        if len(primaries) != 1:
            raise ValueError("decision must have exactly one primary reason")
        primary = primaries[0]
        if reasons[0] != primary:
            raise ValueError("the primary reason must be the first reason code")

        for code in reasons:
            allowed = _QUALIFIER_VALID_PRIMARY.get(code)
            if allowed is not None and primary not in allowed:
                raise ValueError(
                    f"qualifier {code.value!r} is invalid with primary "
                    f"{primary.value!r}"
                )

        if self.decision_type == DecisionType.PRACTICE:
            if self.target_skill is None:
                raise ValueError("practice decision requires target_skill")
            if self.learner_target_band is None:
                raise ValueError("practice decision requires learner_target_band")
            if self.current_estimate is None:
                raise ValueError("practice decision requires current_estimate")
            if PlannerReasonCode.LARGEST_TARGET_GAP not in reasons:
                raise ValueError(
                    "practice decision requires largest_target_gap reason"
                )
        else:
            if self.target_skill is not None:
                raise ValueError("no_practice decision must have null target_skill")
            if self.current_estimate is not None:
                raise ValueError("no_practice decision must have null current_estimate")
            if primary == PlannerReasonCode.TARGET_UNSET:
                if self.learner_target_band is not None:
                    raise ValueError(
                        "target_unset decision must have null learner_target_band"
                    )
            elif self.learner_target_band is None:
                raise ValueError(
                    "no_practice decision (non target_unset) requires "
                    "learner_target_band"
                )

        return self
