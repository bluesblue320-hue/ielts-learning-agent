"""P7-08 mixed planner-version reconstruction and public-boundary tests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.learner.planning_reconstruction import (
    PersistedPlanningReconstructionError,
    reconstruct_persisted_decision,
    reconstruct_persisted_planning_record,
)
from app.memory.episode_queries import reconstruct_decision
from app.memory.errors import MemoryInvariantError
from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillState, LearnerSkillStateSet
from app.schemas.planning import (
    PersistedPlannerContextSnapshot,
    PracticeRecommendationDecision,
    PracticeRecommendationDecisionV2,
)
from tests.test_learning_api import _seed_learner, client, engine
from tests.test_memory_queries import _seed_full_evaluation


DT = datetime(2026, 1, 1, 12, 0, 0)
SKILLS = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)

pytestmark = [pytest.mark.integration]


def _states(*, tied: bool) -> LearnerSkillStateSet:
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


def _decision(*, version: str, tied: bool):
    values = {
        "decision_type": "practice",
        "target_skill": "task_response",
        "learner_target_band": BandScore(value=Decimal("7.0")),
        "current_estimate": Decimal("6.0"),
        "reason_codes": ["largest_target_gap"],
        "planner_version": version,
        "state_snapshot": _states(tied=tied),
    }
    if version == "writing-practice-gap-v1":
        return PracticeRecommendationDecision.model_validate(values)
    return PracticeRecommendationDecisionV2.model_validate(values)


def _snapshot() -> PersistedPlannerContextSnapshot:
    skill_context = {
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
    skill_context["task_response"]["trend"] = "declining"
    return PersistedPlannerContextSnapshot.model_validate(
        {
            "snapshot_version": "writing-practice-gap-memory-v2-audit-v1",
            "memory_context": {
                "memory_version": "writing-memory-v1",
                "progress_version": "writing-progress-v1",
                "memory_context_version": "writing-memory-aware-planning-context-v1",
                "skills": skill_context,
            },
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


def _row(decision, snapshot: PersistedPlannerContextSnapshot | None):
    return SimpleNamespace(
        decision_type=decision.decision_type.value,
        target_skill=decision.target_skill,
        learner_target_band=(
            decision.learner_target_band.value
            if decision.learner_target_band is not None
            else None
        ),
        current_estimate=decision.current_estimate,
        reason_codes=[reason.value for reason in decision.reason_codes],
        planner_version=decision.planner_version,
        state_snapshot=decision.state_snapshot.model_dump(mode="json"),
        planner_context_snapshot=(
            snapshot.model_dump(mode="json") if snapshot else None
        ),
    )


@pytest.mark.parametrize(
    ("version", "tied", "has_snapshot", "expected_type"),
    [
        ("writing-practice-gap-v1", True, False, PracticeRecommendationDecision),
        (
            "writing-practice-gap-memory-v2",
            False,
            False,
            PracticeRecommendationDecisionV2,
        ),
        (
            "writing-practice-gap-memory-v2",
            True,
            True,
            PracticeRecommendationDecisionV2,
        ),
    ],
)
def test_mixed_rows_reconstruct_internal_matrix_and_safe_decision(
    version: str,
    tied: bool,
    has_snapshot: bool,
    expected_type: type,
) -> None:
    decision = _decision(version=version, tied=tied)
    snapshot = _snapshot() if has_snapshot else None
    row = _row(decision, snapshot)

    record = reconstruct_persisted_planning_record(row)
    assert isinstance(record.decision, expected_type)
    assert record.planner_context_snapshot == snapshot
    public_decision = reconstruct_persisted_decision(row)
    assert isinstance(public_decision, expected_type)
    assert not hasattr(public_decision, "planner_context_snapshot")
    if has_snapshot:
        assert public_decision.planning_explanation is not None
        factors = public_decision.planning_explanation.factors
        assert [factor.value for factor in factors] == [
            "equal_maximum_target_gap",
            "trend_tiebreak",
        ]
    elif version == "writing-practice-gap-memory-v2":
        assert public_decision.planning_explanation is None
    else:
        assert "planning_explanation" not in public_decision.model_dump()
    assert isinstance(reconstruct_decision(row), expected_type)


def test_invalid_snapshot_matrix_is_never_silently_repaired() -> None:
    invalid_rows = [
        _row(
            _decision(version="writing-practice-gap-v1", tied=True),
            _snapshot(),
        ),
        _row(
            _decision(version="writing-practice-gap-memory-v2", tied=False),
            _snapshot(),
        ),
        _row(
            _decision(version="writing-practice-gap-memory-v2", tied=True),
            None,
        ),
    ]

    for row in invalid_rows:
        with pytest.raises(PersistedPlanningReconstructionError):
            reconstruct_persisted_planning_record(row)
        with pytest.raises(MemoryInvariantError):
            reconstruct_decision(row)


def test_semantically_impossible_exact_tie_snapshots_are_rejected() -> None:
    decision = _decision(version="writing-practice-gap-memory-v2", tied=True)

    invalid_trend = _snapshot().model_dump(mode="json")
    invalid_trend["memory_context"]["skills"]["task_response"]["trend"] = "stable"

    invalid_recent_practice = _snapshot().model_dump(mode="json")
    invalid_recent_practice["memory_context"]["skills"]["task_response"][
        "trend"
    ] = "stable"
    invalid_recent_practice["selection_trace"]["stages"] = [
        {
            "stage": "persistent_gap",
            "candidates_before": ["task_response", "coherence_and_cohesion"],
            "candidates_after": ["task_response", "coherence_and_cohesion"],
            "narrowed": False,
        },
        {
            "stage": "trend",
            "candidates_before": ["task_response", "coherence_and_cohesion"],
            "candidates_after": ["task_response", "coherence_and_cohesion"],
            "narrowed": False,
        },
        {
            "stage": "recent_practice",
            "candidates_before": ["task_response", "coherence_and_cohesion"],
            "candidates_after": ["task_response"],
            "narrowed": True,
        },
    ]

    invalid_persistent_gap = _snapshot().model_dump(mode="json")
    invalid_persistent_gap["selection_trace"]["stages"] = [
        {
            "stage": "persistent_gap",
            "candidates_before": ["task_response", "coherence_and_cohesion"],
            "candidates_after": ["task_response"],
            "narrowed": True,
        }
    ]

    invalid_priority_reason = _snapshot().model_dump(mode="json")
    invalid_priority_reason["memory_context"]["skills"]["task_response"][
        "trend"
    ] = "stable"
    invalid_priority_reason["selection_trace"]["stages"] = [
        {
            "stage": "persistent_gap",
            "candidates_before": ["task_response", "coherence_and_cohesion"],
            "candidates_after": ["task_response", "coherence_and_cohesion"],
            "narrowed": False,
        },
        {
            "stage": "trend",
            "candidates_before": ["task_response", "coherence_and_cohesion"],
            "candidates_after": ["task_response", "coherence_and_cohesion"],
            "narrowed": False,
        },
        {
            "stage": "recent_practice",
            "candidates_before": ["task_response", "coherence_and_cohesion"],
            "candidates_after": ["task_response", "coherence_and_cohesion"],
            "narrowed": False,
        },
        {
            "stage": "canonical_priority",
            "candidates_before": ["task_response", "coherence_and_cohesion"],
            "candidates_after": ["task_response"],
            "narrowed": True,
        },
    ]

    for snapshot in (
        invalid_trend,
        invalid_recent_practice,
        invalid_persistent_gap,
        invalid_priority_reason,
    ):
        row = _row(
            decision,
            PersistedPlannerContextSnapshot.model_validate(snapshot),
        )
        with pytest.raises(PersistedPlanningReconstructionError):
            reconstruct_persisted_planning_record(row)


def test_valid_exact_tie_snapshot_reconstructs_after_semantic_replay() -> None:
    decision = _decision(version="writing-practice-gap-memory-v2", tied=True)
    record = reconstruct_persisted_planning_record(_row(decision, _snapshot()))

    assert record.decision == decision
    assert record.planner_context_snapshot == _snapshot()


def test_exact_tie_api_projects_v2_decision_without_audit_envelope(
    client,
    engine,
) -> None:
    _seed_learner(engine, learner_id=1)
    _seed_full_evaluation(
        engine,
        evaluation_id=200,
        attempt_id=100,
        bands={
            "task_response": "6.0",
            "coherence_and_cohesion": "6.0",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.5",
        },
    )

    applied = client.post("/learners/1/writing/evaluations/200/apply")
    assert applied.status_code == 200
    episode_id = applied.json()["learning_update_id"]
    detail = client.get(f"/learners/1/writing/history/{episode_id}")
    context = client.get("/learners/1/writing/context")
    assert detail.status_code == 200
    assert context.status_code == 200

    for recommendation in (
        applied.json()["recommendation"],
        detail.json()["recommendation"],
        context.json()["current_recommendation"],
    ):
        assert recommendation["planner_version"] == "writing-practice-gap-memory-v2"
        assert recommendation["planning_explanation"] == {
            "factors": ["equal_maximum_target_gap", "canonical_priority_tiebreak"]
        }
        assert "planner_context_snapshot" not in recommendation
        assert "memory_context" not in recommendation
        assert "selection_trace" not in recommendation
