"""Frozen Writing learner-state taxonomy and state-update policy constants.

This module is the single frozen source of truth for the P3-02 policy
identifiers and constants. It deliberately contains no state-update, replay, or
materialization logic: the production state-update engine is owned by P3-07, and
P3-02 only freezes the policy contract so that later implementation has no
discretion to invent a rule.

See ``docs/WRITING_STATE_POLICY.md`` for the normative policy text.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

# --------------------------------------------------------------------------
# Skill taxonomy
# --------------------------------------------------------------------------

WRITING_SKILL_TAXONOMY_VERSION: Final[str] = "writing-core-v1"

# The exactly-four canonical Writing skills. The tuple order is a stable
# presentation order only; it is not a ranking or a practice priority. P3-08
# owns any skill-priority ordering.
WRITING_SKILLS: Final[tuple[str, ...]] = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)

# --------------------------------------------------------------------------
# State policy
# --------------------------------------------------------------------------

WRITING_STATE_POLICY_VERSION: Final[str] = "writing-state-ewma-v1"

# Frozen EWMA weighting. Alpha is fixed at 0.5 and is not configurable in
# Phase 3 v1. No Bayesian estimation, BKT, IRT, learned weights, or another
# mastery model is permitted.
EWMA_ALPHA: Final[Decimal] = Decimal("0.5")

# Derived-state precision. Intermediate EWMA values are kept as exact Decimal
# values; only the final materialized state is quantized once to STATE_QUANTUM
# using STATE_ROUNDING.
STATE_QUANTUM: Final[Decimal] = Decimal("0.01")
STATE_ROUNDING: Final[str] = ROUND_HALF_UP

# Derived-state bounds. An EWMA of values in [0, 9] is always within
# [0.00, 9.00], so these document the materialized-state range contract.
STATE_MIN: Final[Decimal] = Decimal("0.00")
STATE_MAX: Final[Decimal] = Decimal("9.00")

# --------------------------------------------------------------------------
# Canonical evidence order
# --------------------------------------------------------------------------

# Canonical cross-evaluation ordering comes only from immutable source data and
# never from HTTP request arrival, transaction commit, LearningUpdate/Evidence
# insertion, evidence primary key, or ORM default row order.
#
#   primary key : WritingAttempt.created_at  ascending
#   tie-breaker : WritingAttempt.id          ascending
#
# The source ordering values are copied immutably into LearningEvidence as
# provenance/order data by later nodes so replay does not depend on
# request-processing history.
CANONICAL_ORDER_SOURCE_MODEL: Final[str] = "WritingAttempt"
CANONICAL_ORDER_PRIMARY_FIELD: Final[str] = "created_at"
CANONICAL_ORDER_TIE_BREAKER_FIELD: Final[str] = "id"
CANONICAL_ORDER_DIRECTION: Final[str] = "asc"
