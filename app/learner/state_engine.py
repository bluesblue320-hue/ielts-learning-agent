"""Deterministic Writing learner-state update engine (P3-07).

Implements exactly the frozen P3-02 policy (``writing-state-ewma-v1``) over
canonically ordered criterion evidence:

- EWMA with alpha frozen at ``0.5`` in exact ``Decimal`` arithmetic;
- canonical ordering by ``WritingAttempt.created_at ASC`` then
  ``WritingAttempt.id ASC`` (the immutable source values copied by P3-06);
- full canonical replay/rebuild so arrival order never controls state;
- a single final quantization to ``0.01`` with ``ROUND_HALF_UP`` only after
  the full replay — intermediate values are never rounded;
- initialization to UNOBSERVED with no synthetic prior;
- ``evidence_count`` = number of unique accepted observations;
- last evidence = the observation last in canonical source order.

This is a pure transformation layer: no database, no planner, no LLM. The
engine rebuilds from the complete accepted evidence set; the application layer
(P3-10) owns persistence and revision accounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Iterable, Sequence

from app.learner.writing_evidence import ExtractedWritingEvidence
from app.learner.writing_policy import (
    EWMA_ALPHA,
    STATE_QUANTUM,
    STATE_ROUNDING,
    WRITING_SKILLS,
    WRITING_STATE_POLICY_VERSION,
)
from app.schemas.learner import WritingSkillKey


class WritingStateReplayError(ValueError):
    """Raised when evidence cannot be replayed under the frozen policy.

    Messages identify the violated invariant only; they never dump essay text
    or large source payloads.
    """


@dataclass(frozen=True)
class MaterializedSkillState:
    """The materialized learner-state result for one skill.

    ``estimated_band`` is the final quantized 0.00-9.00 value (or ``None`` for
    UNOBSERVED). ``last_evidence_writing_evaluation_id`` identifies the
    observation last in canonical source order via its immutable source
    evaluation id; P3-10 maps that to the persisted ``LearningEvidence.id``.
    """

    skill: WritingSkillKey
    estimated_band: Decimal | None
    evidence_count: int
    last_evidence_writing_evaluation_id: int | None

    @property
    def observed(self) -> bool:
        return self.estimated_band is not None


def require_state_policy_version(state_policy_version: str) -> None:
    """Reject any state-policy version other than the frozen P3-02 version."""
    if state_policy_version != WRITING_STATE_POLICY_VERSION:
        raise WritingStateReplayError(
            f"unsupported state policy version {state_policy_version!r}; "
            f"engine implements {WRITING_STATE_POLICY_VERSION!r}"
        )


def ewma_estimate(ordered_values: Sequence[Decimal]) -> Decimal:
    """Return the exact, unquantized EWMA estimate over canonically ordered
    values.

    ``S1 = X1`` and ``Sn = 0.5 * Xn + 0.5 * S(n-1)`` using exact Decimal
    arithmetic. Intermediate values are never rounded.
    """

    if not ordered_values:
        raise WritingStateReplayError("cannot compute EWMA over empty evidence")
    estimate = ordered_values[0]
    for value in ordered_values[1:]:
        estimate = value * EWMA_ALPHA + estimate * EWMA_ALPHA
    return estimate


def quantize_materialized(value: Decimal) -> Decimal:
    """Quantize a derived state exactly once to 0.01 with ROUND_HALF_UP."""

    return value.quantize(STATE_QUANTUM, rounding=STATE_ROUNDING)


def canonical_evidence_key(
    item: ExtractedWritingEvidence,
) -> tuple[datetime, int]:
    """Return the immutable canonical-order key (source_created_at, attempt id)."""

    return (item.source_created_at, item.source_attempt_id)


def rebuild_skill_state(
    items: Sequence[ExtractedWritingEvidence],
    *,
    skill: WritingSkillKey,
    state_policy_version: str = WRITING_STATE_POLICY_VERSION,
) -> MaterializedSkillState:
    """Rebuild the materialized state for one skill from ALL accepted evidence.

    The engine never consults existing materialized state as historical truth:
    it re-sorts the complete accepted set into canonical order and replays from
    the first observation. Duplicate canonical evidence for the same skill is
    treated as an invariant violation and rejected, never silently deduplicated.
    """

    require_state_policy_version(state_policy_version)

    skill_items = [item for item in items if item.skill == skill]
    ordered = sorted(skill_items, key=canonical_evidence_key)

    seen: set[tuple[datetime, int]] = set()
    for item in ordered:
        key = canonical_evidence_key(item)
        if key in seen:
            raise WritingStateReplayError(
                f"duplicate canonical evidence for skill {skill!r}: "
                f"source {key[1]} at {key[0].isoformat()}"
            )
        seen.add(key)

    if not ordered:
        return MaterializedSkillState(
            skill=skill,
            estimated_band=None,
            evidence_count=0,
            last_evidence_writing_evaluation_id=None,
        )

    estimate = ewma_estimate([item.observed_band.value for item in ordered])
    return MaterializedSkillState(
        skill=skill,
        estimated_band=quantize_materialized(estimate),
        evidence_count=len(ordered),
        last_evidence_writing_evaluation_id=ordered[-1].writing_evaluation_id,
    )


def rebuild_all_skill_states(
    items: Iterable[ExtractedWritingEvidence],
    *,
    state_policy_version: str = WRITING_STATE_POLICY_VERSION,
) -> dict[WritingSkillKey, MaterializedSkillState]:
    """Rebuild the materialized state for every canonical skill."""

    all_items = list(items)
    return {
        skill: rebuild_skill_state(
            all_items,
            skill=skill,
            state_policy_version=state_policy_version,
        )
        for skill in WRITING_SKILLS
    }
