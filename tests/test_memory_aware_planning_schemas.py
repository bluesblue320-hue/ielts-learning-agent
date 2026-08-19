"""Focused P7-03 contracts for strict memory-aware planner v2 schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillState, LearnerSkillStateSet
from app.schemas.planning import (
    AnyPracticeRecommendationDecision,
    MemoryAwarePlanningContext,
    PersistedPlannerContextSnapshot,
    PersistedRecommendationPlanningRecord,
    PlannerSelectionTrace,
    PracticeRecommendationDecision,
    PracticeRecommendationDecisionV2,
    PublicPlanningExplanation,
)


DT = datetime(2026, 1, 1, 12, 0, 0)
SKILLS = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)


def _states(*, tied: bool = True) -> LearnerSkillStateSet:
    bands = {
        "task_response": "6.0",
        "coherence_and_cohesion": "6.0" if tied else "6.5",
        "lexical_resource": "6.5",
        "grammatical_range_and_accuracy": "6.5",
    }
    return LearnerSkillStateSet(
        **{
            skill: LearnerSkillState(
                learner_id=1,
                skill=skill,
                estimated_band=Decimal(bands[skill]),
                evidence_count=3,
                last_evidence_id=1,
                state_policy_version="writing-state-ewma-v1",
                revision=1,
                updated_at=DT,
            )
            for skill in SKILLS
        }
    )


def _decision_payload(*, version: str, tied: bool = True) -> dict[str, object]:
    return {
        "decision_type": "practice",
        "target_skill": "task_response",
        "learner_target_band": BandScore(value=Decimal("7.0")),
        "current_estimate": Decimal("6.0"),
        "reason_codes": ["largest_target_gap"],
        "planner_version": version,
        "state_snapshot": _states(tied=tied),
    }


def _context() -> MemoryAwarePlanningContext:
    skills = {
        skill: {
            "skill": skill,
            "trend": "stable",
            "persistent_gap": False,
            "persistent_gap_status": "established",
            "recent_practice_count": 0,
            "source_observation_ids": [101, 102, 103],
            "source_episode_ids": [11, 12, 13],
            "recent_practice_source_episode_ids": [13, 12, 11],
        }
        for skill in SKILLS
    }
    return MemoryAwarePlanningContext.model_validate(
        {
            "memory_version": "writing-memory-v1",
            "progress_version": "writing-progress-v1",
            "memory_context_version": "writing-memory-aware-planning-context-v1",
            "skills": skills,
        }
    )


def _snapshot() -> PersistedPlannerContextSnapshot:
    return PersistedPlannerContextSnapshot.model_validate(
        {
            "snapshot_version": "writing-practice-gap-memory-v2-audit-v1",
            "memory_context": _context().model_dump(),
            "selection_trace": {
                "trace_version": "writing-planner-selection-trace-v1",
                "initial_max_gap_candidates": [
                    "task_response",
                    "coherence_and_cohesion",
                ],
                "stages": [
                    {
                        "stage": "persistent_gap",
                        "candidates_before": [
                            "task_response",
                            "coherence_and_cohesion",
                        ],
                        "candidates_after": [
                            "task_response",
                            "coherence_and_cohesion",
                        ],
                        "narrowed": False,
                    },
                    {
                        "stage": "trend",
                        "candidates_before": [
                            "task_response",
                            "coherence_and_cohesion",
                        ],
                        "candidates_after": ["task_response"],
                        "narrowed": True,
                    },
                ],
                "selected_skill": "task_response",
            },
        }
    )


def test_v1_is_still_strict_and_v2_is_discriminated() -> None:
    payload = _decision_payload(version="writing-practice-gap-memory-v2")

    with pytest.raises(ValidationError):
        PracticeRecommendationDecision.model_validate(payload)

    v2 = PracticeRecommendationDecisionV2.model_validate(payload)
    asserted = TypeAdapter(AnyPracticeRecommendationDecision).validate_python(payload)
    assert v2.planner_version == "writing-practice-gap-memory-v2"
    assert isinstance(asserted, PracticeRecommendationDecisionV2)


def test_context_is_input_only_and_requires_complete_shared_recency_window() -> None:
    payload = _context().model_dump()
    payload["selection_trace"] = {"not": "allowed"}
    with pytest.raises(ValidationError, match="selection_trace"):
        MemoryAwarePlanningContext.model_validate(payload)

    payload = _context().model_dump()
    payload["skills"]["lexical_resource"]["recent_practice_source_episode_ids"] = [12, 11]
    with pytest.raises(ValidationError, match="same accepted-update window"):
        MemoryAwarePlanningContext.model_validate(payload)


def test_trace_requires_canonical_candidates_and_ends_at_one_skill() -> None:
    payload = _snapshot().selection_trace.model_dump()
    payload["initial_max_gap_candidates"] = [
        "coherence_and_cohesion",
        "task_response",
    ]
    with pytest.raises(ValidationError, match="canonical"):
        PlannerSelectionTrace.model_validate(payload)

    payload = _snapshot().selection_trace.model_dump()
    payload["stages"][-1]["candidates_after"] = [
        "task_response",
        "coherence_and_cohesion",
    ]
    payload["stages"][-1]["narrowed"] = False
    with pytest.raises(ValidationError, match="resolve to exactly one"):
        PlannerSelectionTrace.model_validate(payload)


def test_snapshot_presence_matrix_is_strict() -> None:
    snapshot = _snapshot()
    v1 = PracticeRecommendationDecision.model_validate(
        _decision_payload(version="writing-practice-gap-v1")
    )
    v2_tie = PracticeRecommendationDecisionV2.model_validate(
        _decision_payload(version="writing-practice-gap-memory-v2")
    )
    v2_unique = PracticeRecommendationDecisionV2.model_validate(
        _decision_payload(version="writing-practice-gap-memory-v2", tied=False)
    )

    assert PersistedRecommendationPlanningRecord(
        decision=v1,
        planner_context_snapshot=None,
    ).planner_context_snapshot is None
    assert PersistedRecommendationPlanningRecord(
        decision=v2_tie,
        planner_context_snapshot=snapshot,
    ).planner_context_snapshot == snapshot
    assert PersistedRecommendationPlanningRecord(
        decision=v2_unique,
        planner_context_snapshot=None,
    ).planner_context_snapshot is None

    with pytest.raises(ValidationError, match="v1 recommendations"):
        PersistedRecommendationPlanningRecord(
            decision=v1,
            planner_context_snapshot=snapshot,
        )
    with pytest.raises(ValidationError, match="exact-tie"):
        PersistedRecommendationPlanningRecord(decision=v2_tie)
    with pytest.raises(ValidationError, match="unique-gap"):
        PersistedRecommendationPlanningRecord(
            decision=v2_unique,
            planner_context_snapshot=snapshot,
        )


def test_public_explanation_cannot_carry_internal_provenance() -> None:
    explanation = PublicPlanningExplanation.model_validate(
        {
            "factors": [
                "equal_maximum_target_gap",
                "trend_tiebreak",
            ]
        }
    )
    assert [factor.value for factor in explanation.factors] == [
        "equal_maximum_target_gap",
        "trend_tiebreak",
    ]

    with pytest.raises(ValidationError):
        PublicPlanningExplanation.model_validate(
            {
                "factors": ["equal_maximum_target_gap"],
                "source_observation_ids": [101],
            }
        )
