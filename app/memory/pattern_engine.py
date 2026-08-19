"""Deterministic L2 longitudinal pattern engine (P6-06).

Pure functions over canonically ordered per-skill observations and learner
episodes, exactly per ``writing-progress-v1``. No LLM, no random behavior, no
hidden weighting, no confidence scores. Trend and persistent-gap decisions are
computed with exact ``Decimal`` arithmetic; the canonical per-skill
observation order is ``source_created_at ASC, source_attempt_id ASC`` (the
caller supplies already-canonically-ordered points).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Sequence

from app.memory.progress_policy import (
    RECENT_PRACTICE_EPISODE_WINDOW,
    TREND_DELTA_THRESHOLD,
    TREND_WINDOW,
)
from app.schemas.memory import (
    LearningEpisodeSummary,
    PersistentGapStatus,
    TrendStatus,
    WritingSkillKey,
)


@dataclass(frozen=True)
class SkillObservationPoint:
    """One canonical per-skill observation (evidence id + band + source time)."""

    learning_evidence_id: int
    observed_band: Decimal
    source_created_at: datetime


@dataclass(frozen=True)
class TrendResult:
    trend: TrendStatus
    delta: Decimal | None = None


@dataclass(frozen=True)
class PersistentGapResult:
    persistent_gap: bool
    status: PersistentGapStatus


def compute_trend(points: Sequence[SkillObservationPoint]) -> TrendResult:
    """Return the frozen ``writing-progress-v1`` trend for a skill.

    Fewer than ``TREND_WINDOW`` observations -> ``insufficient_history``.
    Otherwise delta = last - first within the latest ``TREND_WINDOW`` points,
    with exact Decimal arithmetic and the frozen 0.5 threshold.
    """
    if len(points) < TREND_WINDOW:
        return TrendResult(trend="insufficient_history", delta=None)
    window = points[-TREND_WINDOW:]
    delta = window[-1].observed_band - window[0].observed_band
    if delta >= TREND_DELTA_THRESHOLD:
        return TrendResult(trend="improving", delta=delta)
    if delta <= -TREND_DELTA_THRESHOLD:
        return TrendResult(trend="declining", delta=delta)
    return TrendResult(trend="stable", delta=delta)


def compute_persistent_gap(
    points: Sequence[SkillObservationPoint],
    *,
    current_target_band: Decimal,
) -> PersistentGapResult:
    """Return the frozen current-target-relative persistent gap for a skill.

    Fewer than ``TREND_WINDOW`` observations -> ``false`` +
    ``insufficient_history``. Otherwise all three latest canonical observed
    bands strictly below the learner's CURRENT ``writing_target_band`` ->
    ``true``. The historical ``target_snapshot`` is never substituted.
    """
    if len(points) < TREND_WINDOW:
        return PersistentGapResult(persistent_gap=False, status="insufficient_history")
    window = points[-TREND_WINDOW:]
    below = all(point.observed_band < current_target_band for point in window)
    return PersistentGapResult(persistent_gap=below, status="established")


def recent_observation_count(points: Sequence[SkillObservationPoint]) -> int:
    """Number of canonical observations in the trend window."""
    return min(TREND_WINDOW, len(points))


def latest_observation_time(
    points: Sequence[SkillObservationPoint],
) -> datetime | None:
    """``source_created_at`` of the last canonical observation (or None)."""
    if not points:
        return None
    return points[-1].source_created_at


def trend_source_observation_ids(
    points: Sequence[SkillObservationPoint],
) -> list[int]:
    """The evidence ids of the latest trend-window observations (drill-down)."""
    return [point.learning_evidence_id for point in points[-TREND_WINDOW:]]


def recent_practice_count_for_skill(
    episodes: Sequence[LearningEpisodeSummary],
    *,
    skill: WritingSkillKey,
) -> int:
    """Completed targeted practices for the skill among the latest
    ``RECENT_PRACTICE_EPISODE_WINDOW`` learner-owned L0 episodes.

    A targeted-practice episode implies its linked practice is submitted and
    its evaluation applied (a ``LearningUpdate`` exists), so it counts as
    completed. Episode ordering is the frozen ``LearningUpdate.created_at
    DESC, id DESC`` order (the caller supplies it).
    """
    window = episodes[:RECENT_PRACTICE_EPISODE_WINDOW]
    return sum(
        1
        for episode in window
        if episode.episode_type == "targeted_practice"
        and episode.recommendation_target_skill == skill
    )


def recent_practice_source_episode_ids(
    episodes: Sequence[LearningEpisodeSummary],
) -> list[int]:
    """The episode ids of the recent-practice window (drill-down)."""
    return [episode.episode_id for episode in episodes[:RECENT_PRACTICE_EPISODE_WINDOW]]

