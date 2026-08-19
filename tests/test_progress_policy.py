"""P6-06 pure engine tests for the frozen writing-progress-v1 policy.

These tests encode every normative example in
``docs/WRITING_MEMORY_POLICY.md`` sections 2.1-2.3, plus determinism,
exact-threshold, insufficient-history, current-target, and drill-down
provenance behavior. They exercise no ORM, database, service, or LLM behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.memory.pattern_engine import (
    SkillObservationPoint,
    compute_persistent_gap,
    compute_trend,
    latest_observation_time,
    recent_observation_count,
    recent_practice_count_for_skill,
    recent_practice_source_episode_ids,
    trend_source_observation_ids,
)
from app.memory.progress_policy import (
    RECENT_PRACTICE_EPISODE_WINDOW,
    TREND_DELTA_THRESHOLD,
    TREND_WINDOW,
)
from app.schemas.memory import LearningEpisodeSummary

DT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _points(*bands: str) -> list[SkillObservationPoint]:
    return [
        SkillObservationPoint(
            learning_evidence_id=i + 1,
            observed_band=Decimal(band),
            source_created_at=DT,
        )
        for i, band in enumerate(bands)
    ]


def _episode(episode_id: int, *, etype: str, skill: str | None = "task_response") -> LearningEpisodeSummary:
    return LearningEpisodeSummary(
        episode_id=episode_id,
        episode_type=etype,  # type: ignore[arg-type]
        occurred_at=DT,
        writing_evaluation_id=200 + episode_id,
        attempt_id=100 + episode_id,
        writing_practice_id=episode_id if etype == "targeted_practice" else None,
        recommendation_id=10 + episode_id,
        recommendation_decision_type="practice" if etype == "targeted_practice" else "no_practice",
        recommendation_target_skill=skill,
        recommendation_reason_codes=["largest_target_gap"] if etype == "targeted_practice" else ["cold_start"],
        planner_version="writing-practice-gap-v1",
        skill_observations={
            "task_response": {
                "skill": "task_response",
                "observed_band": {"value": "6.5"},
                "learning_evidence_id": episode_id,
                "source_attempt_id": 100 + episode_id,
                "source_created_at": DT,
            },
            "coherence_and_cohesion": {
                "skill": "coherence_and_cohesion",
                "observed_band": {"value": "6.5"},
                "learning_evidence_id": episode_id,
                "source_attempt_id": 100 + episode_id,
                "source_created_at": DT,
            },
            "lexical_resource": {
                "skill": "lexical_resource",
                "observed_band": {"value": "6.5"},
                "learning_evidence_id": episode_id,
                "source_attempt_id": 100 + episode_id,
                "source_created_at": DT,
            },
            "grammatical_range_and_accuracy": {
                "skill": "grammatical_range_and_accuracy",
                "observed_band": {"value": "6.5"},
                "learning_evidence_id": episode_id,
                "source_attempt_id": 100 + episode_id,
                "source_created_at": DT,
            },
        },
    )


class TestFrozenConstants:
    def test_windows_and_threshold(self) -> None:
        assert TREND_WINDOW == 3
        assert TREND_DELTA_THRESHOLD == Decimal("0.5")
        assert RECENT_PRACTICE_EPISODE_WINDOW == 3


class TestTrendExamples:
    @pytest.mark.parametrize(
        ("bands", "expected_trend", "expected_delta"),
        [
            (["6.0"], "insufficient_history", None),
            (["6.0", "6.5"], "insufficient_history", None),
            (["6.0", "6.5", "7.0"], "improving", Decimal("1.0")),
            (["6.0", "6.5", "6.5"], "improving", Decimal("0.5")),
            (["6.5", "6.0", "6.5"], "stable", Decimal("0.0")),
            (["6.5", "6.5", "6.5"], "stable", Decimal("0.0")),
            (["7.0", "6.5", "6.0"], "declining", Decimal("-1.0")),
            (["7.0", "6.5", "6.5"], "declining", Decimal("-0.5")),
            (["6.0", "6.5", "7.0", "6.5"], "stable", Decimal("0.0")),
            (["6.0", "6.0", "6.5"], "improving", Decimal("0.5")),
        ],
    )
    def test_normative_trend_examples(
        self,
        bands: list[str],
        expected_trend: str,
        expected_delta: Decimal | None,
    ) -> None:
        result = compute_trend(_points(*bands))
        assert result.trend == expected_trend
        assert result.delta == expected_delta

    def test_exact_threshold_boundaries(self) -> None:
        # Exactly +0.5 is improving; exactly -0.5 is declining; 0.0 is stable.
        assert compute_trend(_points("6.0", "6.0", "6.5")).trend == "improving"
        assert compute_trend(_points("6.5", "6.5", "6.0")).trend == "declining"
        assert compute_trend(_points("6.0", "6.5", "6.0")).trend == "stable"

    def test_window_uses_latest_three(self) -> None:
        # 6.0, 6.5, 7.0, 6.5 -> window [6.5, 7.0, 6.5] -> delta 0 -> stable
        assert compute_trend(_points("6.0", "6.5", "7.0", "6.5")).trend == "stable"

    def test_input_is_a_sequence_function(self) -> None:
        # Deterministic pure function: same canonical input, same result.
        a = compute_trend(_points("6.0", "6.5", "7.0"))
        b = compute_trend(_points("6.0", "6.5", "7.0"))
        assert a == b


class TestPersistentGapExamples:
    @pytest.mark.parametrize(
        ("bands", "expected_gap", "expected_status"),
        [
            (["6.0", "6.5"], False, "insufficient_history"),
            (["6.0", "6.5", "6.5"], True, "established"),
            (["6.0", "7.0", "6.5"], False, "established"),
            (["7.0", "7.5", "8.0"], False, "established"),
            (["5.5", "6.0", "7.0"], False, "established"),
        ],
    )
    def test_normative_gap_examples(
        self,
        bands: list[str],
        expected_gap: bool,
        expected_status: str,
    ) -> None:
        result = compute_persistent_gap(_points(*bands), current_target_band=Decimal("7.0"))
        assert result.persistent_gap == expected_gap
        assert result.status == expected_status

    def test_gap_is_current_target_relative(self) -> None:
        points = _points("6.0", "6.5", "6.5")
        assert compute_persistent_gap(points, current_target_band=Decimal("7.0")).persistent_gap is True
        assert compute_persistent_gap(points, current_target_band=Decimal("6.0")).persistent_gap is False

    def test_insufficient_history(self) -> None:
        result = compute_persistent_gap(_points("6.0", "6.5"), current_target_band=Decimal("7.0"))
        assert result.persistent_gap is False
        assert result.status == "insufficient_history"


class TestCountsAndProvenance:
    def test_recent_observation_count(self) -> None:
        assert recent_observation_count(_points()) == 0
        assert recent_observation_count(_points("6.0")) == 1
        assert recent_observation_count(_points("6.0", "6.5")) == 2
        assert recent_observation_count(_points("6.0", "6.5", "6.5")) == 3
        assert recent_observation_count(_points("6.0", "6.5", "6.5", "7.0")) == 3

    def test_latest_observation_time(self) -> None:
        assert latest_observation_time([]) is None
        assert latest_observation_time(_points("6.0", "6.5")) == DT

    def test_trend_source_observation_ids(self) -> None:
        points = _points("6.0", "6.5", "6.5", "7.0")
        assert trend_source_observation_ids(points) == [2, 3, 4]
        assert trend_source_observation_ids(_points("6.0", "6.5")) == [1, 2]

    def test_recent_practice_count_window(self) -> None:
        episodes = [
            _episode(7, etype="targeted_practice", skill="task_response"),
            _episode(6, etype="targeted_practice", skill="lexical_resource"),
            _episode(5, etype="initial_writing", skill=None),
            _episode(4, etype="targeted_practice", skill="task_response"),  # outside window
        ]
        # Only the latest 3 episodes count.
        assert recent_practice_count_for_skill(episodes, skill="task_response") == 1
        assert recent_practice_count_for_skill(episodes, skill="lexical_resource") == 1
        assert recent_practice_count_for_skill(episodes, skill="grammatical_range_and_accuracy") == 0
        assert recent_practice_source_episode_ids(episodes) == [7, 6, 5]

    def test_recent_practice_window_constant_is_separate(self) -> None:
        # 4 targeted practices: only the latest RECENT_PRACTICE_EPISODE_WINDOW count.
        episodes = [
            _episode(9, etype="targeted_practice", skill="task_response"),
            _episode(8, etype="targeted_practice", skill="task_response"),
            _episode(7, etype="targeted_practice", skill="task_response"),
            _episode(6, etype="targeted_practice", skill="task_response"),
        ]
        assert RECENT_PRACTICE_EPISODE_WINDOW == 3
        assert recent_practice_count_for_skill(episodes, skill="task_response") == 3
