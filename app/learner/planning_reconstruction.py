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
from app.learner.memory_planner import (
    resolve_practice_v2_exact_tie,
    select_practice_v2_base,
)
from app.learner.planning_policy import PLANNER_VERSION
from app.models.learning import PracticeRecommendation
from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillStateSet
from app.schemas.planning import (
    DecisionType,
    PersistedPlannerContextSnapshot,
    PersistedRecommendationPlanningRecord,
    PlanningExplanationFactor,
    PlannerReasonCode,
    PublicPlanningExplanation,
    PublicPracticeRecommendationDecision,
    PublicPracticeRecommendationDecisionV2,
    PracticeRecommendationDecision,
    PracticeRecommendationDecisionV2,
)


class PersistedPlanningReconstructionError(ValueError):
    """A stored recommendation does not satisfy its versioned contract."""


def _validate_v2_snapshot_semantics(
    record: PersistedRecommendationPlanningRecord,
) -> None:
    """Replay a stored exact-tie envelope without consulting current Memory.

    Structural schema validation proves that an envelope has the expected
    shape. This replay additionally proves that its immutable context could
    have produced both the persisted v2 decision and its complete trace.
    """

    decision = record.decision
    snapshot = record.planner_context_snapshot
    if (
        decision.planner_version != PLANNER_V2_VERSION
        or decision.decision_type != DecisionType.PRACTICE
        or snapshot is None
    ):
        return

    assert decision.learner_target_band is not None
    base_selection = select_practice_v2_base(
        learner_target_band=decision.learner_target_band,
        states=decision.state_snapshot,
    )
    if not base_selection.requires_memory_context:
        raise PersistedPlanningReconstructionError(
            "v2 planner snapshot exists without an exact maximum-gap tie"
        )
    if (
        list(base_selection.exact_max_gap_candidates)
        != snapshot.selection_trace.initial_max_gap_candidates
    ):
        raise PersistedPlanningReconstructionError(
            "v2 planner snapshot candidates differ from the replayed exact tie"
        )

    expected = resolve_practice_v2_exact_tie(
        base_selection=base_selection,
        memory_context=snapshot.memory_context,
    )
    if (
        expected.decision != decision
        or expected.selection_trace != snapshot.selection_trace
    ):
        raise PersistedPlanningReconstructionError(
            "persisted v2 planner snapshot is not semantically self-consistent"
        )


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
        record = PersistedRecommendationPlanningRecord(
            decision=decision,
            planner_context_snapshot=snapshot,
        )
        _validate_v2_snapshot_semantics(record)
        return record
    except (ArithmeticError, TypeError, ValidationError, ValueError) as error:
        if isinstance(error, PersistedPlanningReconstructionError):
            raise
        raise PersistedPlanningReconstructionError(
            "persisted recommendation violates planner contract"
        ) from error


_TRACE_FACTORS = {
    "persistent_gap": PlanningExplanationFactor.PERSISTENT_GAP_TIEBREAK,
    "trend": PlanningExplanationFactor.TREND_TIEBREAK,
    "recent_practice": PlanningExplanationFactor.LOWER_RECENT_PRACTICE_COUNT,
    "canonical_priority": (
        PlanningExplanationFactor.CANONICAL_PRIORITY_TIEBREAK
    ),
}


def _planning_explanation_from_snapshot(
    snapshot: PersistedPlannerContextSnapshot | None,
) -> PublicPlanningExplanation | None:
    """Project only semantic tie-break facts from the immutable trace."""

    if snapshot is None:
        return None
    factors = [PlanningExplanationFactor.EQUAL_MAXIMUM_TARGET_GAP]
    for stage in snapshot.selection_trace.stages:
        if stage.narrowed:
            factors.append(_TRACE_FACTORS[stage.stage])
    return PublicPlanningExplanation(factors=factors)


def reconstruct_persisted_decision(
    row: PracticeRecommendation,
) -> PublicPracticeRecommendationDecision:
    """Return a safe public v1/v2 decision from the immutable record."""

    record = reconstruct_persisted_planning_record(row)
    decision = record.decision
    if decision.planner_version == PLANNER_VERSION:
        return decision
    return PublicPracticeRecommendationDecisionV2(
        **decision.model_dump(),
        planning_explanation=_planning_explanation_from_snapshot(
            record.planner_context_snapshot
        ),
    )
