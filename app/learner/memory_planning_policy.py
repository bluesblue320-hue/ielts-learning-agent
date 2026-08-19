"""Frozen Phase 7 memory-aware planner v2 constants.

These are planner-owned identifiers and the accepted-update recency window.
They do not alter the frozen v1 planner or Phase 6 ``writing-progress-v1``.
"""

from __future__ import annotations

from typing import Final


PLANNER_V2_VERSION: Final[str] = "writing-practice-gap-memory-v2"
MEMORY_CONTEXT_VERSION: Final[str] = "writing-memory-aware-planning-context-v1"
SELECTION_TRACE_VERSION: Final[str] = "writing-planner-selection-trace-v1"
PLANNER_SNAPSHOT_VERSION: Final[str] = "writing-practice-gap-memory-v2-audit-v1"

# Planner-owned accepted-update recency. This is deliberately independent from
# Phase 6's public writing-progress-v1 episode-recency definition.
PLANNING_RECENT_PRACTICE_WINDOW: Final[int] = 3
