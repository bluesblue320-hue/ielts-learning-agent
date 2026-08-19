"""Frozen L2 progress-policy constants (P6-06, ``writing-progress-v1``).

These constants mirror the normative policy in
``docs/WRITING_MEMORY_POLICY.md`` sections 1.9-1.11 exactly and contain no
engine logic. ``RECENT_PRACTICE_EPISODE_WINDOW`` is an independently versioned
concept and MUST NOT be defined in terms of ``TREND_WINDOW`` even though both
are ``3`` in v1.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, Literal

# The number of canonical observations that define one trend/persistent-gap
# window. Fewer than this is `insufficient_history`.
TREND_WINDOW: Final[int] = 3

# Trend delta threshold: observed bands are IELTS half-bands, so the smallest
# non-zero delta is 0.5. A 0.25 threshold would be finer than data granularity
# and is forbidden for writing-progress-v1.
TREND_DELTA_THRESHOLD: Final[Decimal] = Decimal("0.5")

# The number of most-recent learner-owned L0 episodes that define the recent
# completed-practice window. Separate concept from TREND_WINDOW.
RECENT_PRACTICE_EPISODE_WINDOW: Final[int] = 3

PROGRESS_POLICY_VERSION: Literal["writing-progress-v1"] = "writing-progress-v1"
