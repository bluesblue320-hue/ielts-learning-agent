"""P3-02 boundary and example tests for the frozen Writing state policy.

These tests encode the accepted P3-02 decisions using a test-local reference
calculator. They import no Phase 3 production schema, model, service, updater,
planner, or API, and they introduce no runtime implementation for P3-03 or
later nodes.

The reference calculator reproduces the frozen policy so the tests prove the
normative contract without duplicating the production state-update engine
(which P3-07 owns).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

import pytest
from pydantic import ValidationError

from app.learner import writing_policy as policy
from app.schemas.common import BandScore


# ---------------------------------------------------------------------------
# Test-local reference calculator
# ---------------------------------------------------------------------------


class ReferencePolicyError(Exception):
    """A P3-02 invariant was violated during reference replay."""


class MissingCriterionError(ReferencePolicyError):
    """An evaluation did not yield exactly the four canonical criteria."""


class DuplicateEvidenceError(ReferencePolicyError):
    """Duplicate canonical evidence exists in persisted history."""


@dataclass(frozen=True)
class ReferenceEvidence:
    """One canonical criterion observation with immutable order provenance.

    ``evidence_id`` stands in for the future LearningEvidence primary key;
    canonical ordering is never derived from it.
    """

    evidence_id: int
    evaluation_id: int
    skill: str
    observed_band: Decimal
    created_at: datetime
    attempt_id: int


@dataclass(frozen=True)
class ReferenceEvaluation:
    """One accepted WritingEvaluation: four criterion bands plus order keys."""

    evaluation_id: int
    created_at: datetime
    attempt_id: int
    bands: dict[str, Decimal]


@dataclass(frozen=True)
class ReferenceState:
    """Materialized reference state for one skill after canonical replay."""

    estimated: Decimal | None
    evidence_count: int
    last_evidence_id: int | None
    exact: Decimal | None  # unquantized S_n, retained for precision checks


def _canonical_sort_key(evidence: ReferenceEvidence) -> tuple[datetime, int]:
    return (evidence.created_at, evidence.attempt_id)


def canonical_replay(evidence: Sequence[ReferenceEvidence]) -> ReferenceState:
    """Replay one skill's accepted evidence in canonical source order.

    Sorts by (created_at ASC, attempt_id ASC), never by evidence_id or input
    order. Duplicate (evaluation_id, skill) evidence raises
    DuplicateEvidenceError and is never silently deduplicated.
    """

    seen: set[tuple[int, str]] = set()
    for item in evidence:
        identity = (item.evaluation_id, item.skill)
        if identity in seen:
            raise DuplicateEvidenceError(
                f"duplicate evidence for evaluation {item.evaluation_id} "
                f"skill {item.skill!r}"
            )
        seen.add(identity)

    ordered = sorted(evidence, key=_canonical_sort_key)
    if not ordered:
        return ReferenceState(None, 0, None, None)

    state = ordered[0].observed_band
    for item in ordered[1:]:
        state = (
            policy.EWMA_ALPHA * item.observed_band
            + (Decimal("1") - policy.EWMA_ALPHA) * state
        )

    estimated = state.quantize(policy.STATE_QUANTUM, rounding=policy.STATE_ROUNDING)
    return ReferenceState(
        estimated=estimated,
        evidence_count=len(ordered),
        last_evidence_id=ordered[-1].evidence_id,
        exact=state,
    )


def validate_evaluation(evaluation: ReferenceEvaluation) -> None:
    """Require exactly the four canonical criterion bands; 3/4 is invalid."""

    missing = [skill for skill in policy.WRITING_SKILLS if skill not in evaluation.bands]
    extra = [key for key in evaluation.bands if key not in policy.WRITING_SKILLS]
    if missing or extra:
        raise MissingCriterionError(
            f"evaluation {evaluation.evaluation_id} has missing={missing} extra={extra}"
        )


@dataclass
class ReferenceSkillLedger:
    """Minimal test-local model of revision and idempotency semantics."""

    skill: str
    evidence: list[ReferenceEvidence] = field(default_factory=list)
    _applied_evaluations: set[int] = field(default_factory=set)
    revision: int = 0

    @property
    def state(self) -> ReferenceState:
        return canonical_replay(self.evidence)

    def apply(self, evaluation: ReferenceEvaluation) -> ReferenceState:
        """Apply one accepted evaluation to this skill, honoring idempotency."""

        if evaluation.evaluation_id in self._applied_evaluations:
            return self.state  # idempotent: no new evidence, no revision bump
        validate_evaluation(evaluation)
        self._applied_evaluations.add(evaluation.evaluation_id)
        skill_index = policy.WRITING_SKILLS.index(self.skill)
        self.evidence.append(
            ReferenceEvidence(
                evidence_id=evaluation.evaluation_id * 10 + skill_index,
                evaluation_id=evaluation.evaluation_id,
                skill=self.skill,
                observed_band=evaluation.bands[self.skill],
                created_at=evaluation.created_at,
                attempt_id=evaluation.attempt_id,
            )
        )
        self.revision += 1
        return self.state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dt(day: int, second: int = 0) -> datetime:
    return datetime(2026, 1, 1) + timedelta(days=day - 1, seconds=second)


def evidence(
    evidence_id: int,
    evaluation_id: int,
    skill: str,
    band: str,
    created_at: datetime,
    attempt_id: int,
) -> ReferenceEvidence:
    return ReferenceEvidence(
        evidence_id=evidence_id,
        evaluation_id=evaluation_id,
        skill=skill,
        observed_band=Decimal(band),
        created_at=created_at,
        attempt_id=attempt_id,
    )


def evaluation(
    evaluation_id: int,
    created_at: datetime,
    attempt_id: int,
    bands: dict[str, str],
) -> ReferenceEvaluation:
    return ReferenceEvaluation(
        evaluation_id=evaluation_id,
        created_at=created_at,
        attempt_id=attempt_id,
        bands={skill: Decimal(value) for skill, value in bands.items()},
    )


ALL_FOUR = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)


# ---------------------------------------------------------------------------
# 1/2/3. Taxonomy and version freezes
# ---------------------------------------------------------------------------


def test_taxonomy_contains_exactly_four_canonical_skills() -> None:
    assert policy.WRITING_SKILL_TAXONOMY_VERSION == "writing-core-v1"
    assert len(policy.WRITING_SKILLS) == 4
    assert set(policy.WRITING_SKILLS) == set(ALL_FOUR)


def test_state_policy_version_is_exact() -> None:
    assert policy.WRITING_STATE_POLICY_VERSION == "writing-state-ewma-v1"


def test_alpha_is_exact_half_and_not_configurable() -> None:
    assert policy.EWMA_ALPHA == Decimal("0.5")


# ---------------------------------------------------------------------------
# 4/5/6/7. Precision, rounding, half-band vs derived-state split
# ---------------------------------------------------------------------------


def test_source_evidence_preserves_half_band_semantics() -> None:
    assert BandScore(value=Decimal("6.5")).value == Decimal("6.5")
    assert BandScore(value=Decimal("0")).value == Decimal("0")
    assert BandScore(value=Decimal("9")).value == Decimal("9")

    with pytest.raises(ValidationError):
        BandScore(value=Decimal("5.3"))
    with pytest.raises(ValidationError):
        BandScore(value=Decimal("9.5"))
    with pytest.raises(ValidationError):
        BandScore(value=Decimal("5.25"))


def test_derived_state_is_not_forced_to_half_band() -> None:
    assert policy.STATE_QUANTUM == Decimal("0.01")
    assert policy.STATE_QUANTUM != Decimal("0.5")

    result = canonical_replay(
        [
            evidence(1, 1, "lexical_resource", "6.0", _dt(1), 1),
            evidence(2, 2, "lexical_resource", "6.5", _dt(2), 2),
            evidence(3, 3, "lexical_resource", "7.0", _dt(3), 3),
        ]
    )
    assert result.estimated == Decimal("6.63")
    assert result.estimated % Decimal("0.5") != 0


def test_final_quantization_uses_round_half_up_once() -> None:
    assert policy.STATE_ROUNDING == ROUND_HALF_UP

    result = canonical_replay(
        [
            evidence(1, 1, "task_response", "6.0", _dt(1), 1),
            evidence(2, 2, "task_response", "6.5", _dt(2), 2),
            evidence(3, 3, "task_response", "7.0", _dt(3), 3),
        ]
    )
    # The exact intermediate is preserved; only the final value is quantized.
    assert result.exact == Decimal("6.625")
    assert result.estimated == Decimal("6.63")


# ---------------------------------------------------------------------------
# 7/8/9/10. UNOBSERVED, no decay, no outliers, no confidence
# ---------------------------------------------------------------------------


def test_no_evidence_is_unobserved() -> None:
    result = canonical_replay([])
    assert result.estimated is None
    assert result.evidence_count == 0
    assert result.last_evidence_id is None


def test_no_wall_clock_decay() -> None:
    close_gap = [
        evidence(1, 1, "lexical_resource", "6.5", _dt(1), 1),
        evidence(2, 2, "lexical_resource", "6.5", _dt(1, 1), 2),
    ]
    long_gap = [
        evidence(1, 1, "lexical_resource", "6.5", _dt(1), 1),
        evidence(2, 2, "lexical_resource", "6.5", _dt(1) + timedelta(days=30), 2),
    ]

    assert canonical_replay(close_gap).estimated == Decimal("6.50")
    assert canonical_replay(long_gap).estimated == Decimal("6.50")
    assert canonical_replay(close_gap).estimated == canonical_replay(long_gap).estimated


def test_no_outlier_filtering() -> None:
    result = canonical_replay(
        [
            evidence(1, 1, "task_response", "6.5", _dt(1), 1),
            evidence(2, 2, "task_response", "6.5", _dt(2), 2),
            evidence(3, 3, "task_response", "6.5", _dt(3), 3),
            evidence(4, 4, "task_response", "4.5", _dt(4), 4),
        ]
    )
    assert result.estimated == Decimal("5.50")
    assert result.evidence_count == 4


def test_no_confidence_in_v1() -> None:
    assert not hasattr(policy, "CONFIDENCE")
    result = canonical_replay([evidence(1, 1, "lexical_resource", "6.5", _dt(1), 1)])
    assert not hasattr(result, "confidence")


# ---------------------------------------------------------------------------
# 12/13. Canonical ordering and tie-breaking
# ---------------------------------------------------------------------------


def test_canonical_order_is_created_at_asc_then_id_asc() -> None:
    assert policy.CANONICAL_ORDER_SOURCE_MODEL == "WritingAttempt"
    assert policy.CANONICAL_ORDER_PRIMARY_FIELD == "created_at"
    assert policy.CANONICAL_ORDER_TIE_BREAKER_FIELD == "id"
    assert policy.CANONICAL_ORDER_DIRECTION == "asc"


def test_same_timestamp_ties_break_on_id() -> None:
    same_time = _dt(5)
    ordered = sorted(
        [
            evidence(2, 2, "lexical_resource", "7.0", same_time, 101),
            evidence(1, 1, "lexical_resource", "6.0", same_time, 100),
        ],
        key=_canonical_sort_key,
    )
    assert [item.attempt_id for item in ordered] == [100, 101]


def test_ordering_prefers_earlier_created_at_over_id() -> None:
    ordered = sorted(
        [
            evidence(1, 1, "lexical_resource", "7.0", _dt(2), 1),
            evidence(2, 2, "lexical_resource", "6.0", _dt(1), 999),
        ],
        key=_canonical_sort_key,
    )
    assert [item.attempt_id for item in ordered] == [999, 1]


# ---------------------------------------------------------------------------
# 13. Canonical-order independence and late arrival
# ---------------------------------------------------------------------------


def test_replay_is_independent_of_application_order() -> None:
    a = evidence(1, 1, "lexical_resource", "6.0", _dt(1), 100)
    b = evidence(2, 2, "lexical_resource", "7.0", _dt(2), 101)

    forward = canonical_replay([a, b])
    late_arrival = canonical_replay([b, a])

    assert forward.estimated == Decimal("6.50")
    assert late_arrival.estimated == forward.estimated
    assert late_arrival.last_evidence_id == b.evidence_id


# ---------------------------------------------------------------------------
# 14. Duplicate evidence is an invariant violation, never deduplicated
# ---------------------------------------------------------------------------


def test_duplicate_evidence_is_an_invariant_violation() -> None:
    a = evidence(1, 1, "lexical_resource", "6.0", _dt(1), 1)
    duplicate = evidence(2, 1, "lexical_resource", "6.0", _dt(1), 1)

    with pytest.raises(DuplicateEvidenceError):
        canonical_replay([a, duplicate])


# ---------------------------------------------------------------------------
# 15. Missing evidence invalidates the whole update
# ---------------------------------------------------------------------------


def test_missing_criterion_invalidates_whole_update() -> None:
    three_of_four = {
        "task_response": "6.5",
        "coherence_and_cohesion": "6.5",
        "lexical_resource": "6.5",
    }
    with pytest.raises(MissingCriterionError):
        validate_evaluation(evaluation(1, _dt(1), 1, three_of_four))


def test_ledger_rejects_partial_update_without_mutation() -> None:
    ledger = ReferenceSkillLedger("grammatical_range_and_accuracy")
    three_of_four = evaluation(
        1,
        _dt(1),
        1,
        {"task_response": "6.5", "coherence_and_cohesion": "6.5", "lexical_resource": "6.5"},
    )

    with pytest.raises(MissingCriterionError):
        ledger.apply(three_of_four)

    assert ledger.revision == 0
    assert ledger.state.estimated is None
    assert ledger.state.evidence_count == 0


# ---------------------------------------------------------------------------
# 16/17/18. evidence_count, last_evidence_id, revision
# ---------------------------------------------------------------------------


def test_evidence_count_counts_unique_accepted_observations() -> None:
    ledger = ReferenceSkillLedger("lexical_resource")
    for i in range(1, 5):
        ledger.apply(evaluation(i, _dt(i), i, {skill: "6.5" for skill in ALL_FOUR}))

    assert ledger.state.evidence_count == 4
    assert ledger.revision == 4


def test_idempotent_reapply_does_not_increment_count_or_revision() -> None:
    first = evaluation(1, _dt(1), 1, {skill: "6.5" for skill in ALL_FOUR})
    second = evaluation(2, _dt(2), 2, {skill: "6.5" for skill in ALL_FOUR})
    ledger = ReferenceSkillLedger("task_response")

    ledger.apply(first)
    assert ledger.revision == 1

    ledger.apply(second)
    assert ledger.revision == 2
    assert ledger.state.evidence_count == 2

    ledger.apply(first)  # idempotent
    assert ledger.revision == 2
    assert ledger.state.evidence_count == 2


def test_last_evidence_id_is_canonical_latest_not_insertion_latest() -> None:
    # Canonical order: A (older) -> B (newer). B is inserted first.
    a = evidence(1, 1, "lexical_resource", "6.0", _dt(1), 100)
    b = evidence(2, 2, "lexical_resource", "7.0", _dt(2), 101)

    result = canonical_replay([b, a])

    assert result.last_evidence_id == b.evidence_id


def test_revision_increments_on_late_arriving_older_evidence() -> None:
    newer = evaluation(2, _dt(2), 2, {skill: "7.0" for skill in ALL_FOUR})
    older = evaluation(1, _dt(1), 1, {skill: "6.0" for skill in ALL_FOUR})
    ledger = ReferenceSkillLedger("lexical_resource")

    ledger.apply(newer)  # revision 1
    assert ledger.revision == 1

    ledger.apply(older)  # late arrival causes canonical replay; revision 2
    assert ledger.revision == 2
    # Canonical replay(A, B) -> S2 = 6.5
    assert ledger.state.estimated == Decimal("6.50")
    assert ledger.state.last_evidence_id == 2 * 10 + policy.WRITING_SKILLS.index("lexical_resource")


# ---------------------------------------------------------------------------
# 17. Required policy examples
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["6.5"], "6.50"),
        (["6.5", "6.5", "6.5"], "6.50"),
        (["6.0", "6.5", "7.0"], "6.63"),
        (["7.0", "6.5", "6.0"], "6.38"),
        (["6.0", "6.5", "7.0", "6.5"], "6.56"),
        (["0.0"], "0.00"),
        (["9.0"], "9.00"),
    ],
)
def test_required_numeric_examples(values: list[str], expected: str) -> None:
    items = [
        evidence(i + 1, i + 1, "lexical_resource", value, _dt(i + 1), i + 1)
        for i, value in enumerate(values)
    ]
    assert canonical_replay(items).estimated == Decimal(expected)


def test_example_h_canonical_order_independence() -> None:
    a = evidence(1, 1, "lexical_resource", "6.0", _dt(1), 100)
    b = evidence(2, 2, "lexical_resource", "7.0", _dt(2), 101)

    assert canonical_replay([a, b]).estimated == Decimal("6.50")
    assert canonical_replay([b, a]).estimated == Decimal("6.50")


def test_example_i_same_timestamp_tie_order() -> None:
    same_time = _dt(5)
    a = evidence(1, 1, "lexical_resource", "6.0", same_time, 100)
    b = evidence(2, 2, "lexical_resource", "7.0", same_time, 101)

    ordered = sorted([b, a], key=_canonical_sort_key)
    assert [item.attempt_id for item in ordered] == [100, 101]
    assert canonical_replay([b, a]).estimated == Decimal("6.50")


def test_example_j_no_evidence_is_unobserved() -> None:
    result = canonical_replay([])
    assert result.estimated is None
    assert result.evidence_count == 0
