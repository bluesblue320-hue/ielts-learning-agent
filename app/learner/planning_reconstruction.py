"""Version-aware reconstruction of persisted planner recommendation rows.

This is the internal persistence boundary for the frozen v1/v2 recommendation
contracts.  It validates the conditional P7 audit-envelope presence matrix
before returning a public decision model; callers must never expose the raw
envelope in normal product responses.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import ValidationError

from app.learner.memory_planning_policy import PLANNER_V2_VERSION
from app.learner.planning_policy import PLANNER_VERSION
from app.models.learning import PracticeRecommendation
from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillStateSet
from app.schemas.planning import (
    AnyPracticeRecommendationDecision,
    DecisionType,
    PersistedPlannerContextSnapshot,
    PersistedRecommendationPlanningRecord,
    PlannerReasonCode,
    PracticeRecommendationDecision,
    PracticeRecommendationDecisionV2,
)


class PersistedPlanningReconstructionError(ValueError):
    """A stored recommendation does not satisfy its versioned contract."""


def reconstruct_persisted_planning_record(
    row: PracticeRecommendation,
) -> PersistedRecommendationPlanningRecord:
    """Rebuild and strictly validate one immutable v1 or v2 row."""

    try:
        decision_values = {
            "decision_type": DecisionType(row.decision_type),
            "target_skill": row.target_skill,
            "learner_target_band": (
                BandScore(value=Decimal(row.learner_target_band))
                if row.learner_target_band is not None
                else None
            ),
            "current_estimate": row.current_estimate,
            "reason_codes": [PlannerReasonCode(code) for code in row.reason_codes],
            "planner_version": row.planner_version,
            "state_snapshot": LearnerSkillStateSet.model_validate(row.state_snapshot),
        }
        if row.planner_version == PLANNER_VERSION:
            decision = PracticeRecommendationDecision(**decision_values)
        elif row.planner_version == PLANNER_V2_VERSION:
            decision = PracticeRecommendationDecisionV2(**decision_values)
        else:
            raise PersistedPlanningReconstructionError(
                "unsupported persisted planner version"
            )
        snapshot = (
            PersistedPlannerContextSnapshot.model_validate(
                row.planner_context_snapshot
            )
            if row.planner_context_snapshot is not None
            else None
        )
        return PersistedRecommendationPlanningRecord(
            decision=decision,
            planner_context_snapshot=snapshot,
        )
    except (ArithmeticError, TypeError, ValidationError, ValueError) as error:
        if isinstance(error, PersistedPlanningReconstructionError):
            raise
        raise PersistedPlanningReconstructionError(
            "persisted recommendation violates planner contract"
        ) from error


def reconstruct_persisted_decision(
    row: PracticeRecommendation,
) -> AnyPracticeRecommendationDecision:
    """Return the safe public v1/v2 decision without its audit envelope."""

    return reconstruct_persisted_planning_record(row).decision
