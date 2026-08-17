"""Frozen Writing practice-planning policy constants (P3-08).

This module freezes only the P3-08 planner policy identifiers and constants. It
contains no decision algorithm; the production planner implementation is owned
by P3-09. The planner's only responsibility is selecting what Writing skill to
practice next, or deterministically recording that no evidence-based target is
required.

See ``docs/PRACTICE_PLANNING_POLICY.md`` for the normative policy text.
"""

from typing import Final

PLANNER_VERSION: Final[str] = "writing-practice-gap-v1"

# 0 evidence = unobserved; 1-2 = insufficient; >= 3 = established for v1.
MIN_ESTABLISHED_EVIDENCE_COUNT: Final[int] = 3

# Explicit planning tie-break priority. Used ONLY when two or more candidate
# skills share exactly the same maximum positive target gap. It is not a claim
# that one IELTS criterion is academically more important than another.
PRACTICE_TIEBREAK_PRIORITY: Final[tuple[str, ...]] = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)

# Reason-code taxonomy (planner v1). Primary reasons come first in any decision.
REASON_LARGEST_TARGET_GAP: Final[str] = "largest_target_gap"
REASON_PRIORITY_TIEBREAK: Final[str] = "priority_tiebreak"
REASON_INSUFFICIENT_EVIDENCE: Final[str] = "insufficient_evidence"
REASON_TARGET_ACHIEVED: Final[str] = "target_achieved"
REASON_COLD_START: Final[str] = "cold_start"
REASON_INCOMPLETE_STATE: Final[str] = "incomplete_state"
REASON_TARGET_UNSET: Final[str] = "target_unset"

# Decision types.
DECISION_PRACTICE: Final[str] = "practice"
DECISION_NO_PRACTICE: Final[str] = "no_practice"
