"""Focused tests for the P3-07 deterministic learner-state replay engine."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.learner.state_engine import (
    MaterializedSkillState,
    WritingStateReplayError,
    ewma_estimate,
    quantize_materialized,
    rebuild_all_skill_states,
    rebuild_skill_state,
    require_state_policy_version,
)
from app.learner.writing_evidence import (
    ExtractedWritingEvidence,
    ExtractedWritingEvidenceSet,
    extract_writing_evidence,
)
from app.learner.writing_policy import WRITING_SKILLS
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.common import BandScore
from app.schemas.writing import EvaluationMetadata

T1 = datetime(2026, 1, 10, 9, 30, tzinfo=timezone.utc)
T2 = datetime(2026, 1, 12, 18, 45, tzinfo=timezone.utc)
T3 = datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc)
T4 = datetime(2026, 2, 3, 21, 15, tzinfo=timezone.utc)

PROVENANCE = EvaluationMetadata(
    provider="deepseek",
    model="deepseek-chat",
    prompt_version="writing-v2",
    rubric_version="writing-task2-v1",
    scoring_policy_version="writing-scoring-v1",
    thinking_mode="disabled",
)


def item(
    skill: str,
    band: str,
    *,
    evaluation_id: int,
    source_created_at: datetime,
    source_attempt_id: int,
) -> ExtractedWritingEvidence:
    return ExtractedWritingEvidence(
        writing_evaluation_id=evaluation_id,
        skill=skill,
        observed_band=BandScore(value=Decimal(band)),
        source_created_at=source_created_at,
        source_attempt_id=source_attempt_id,
        provenance=PROVENANCE,
    )


def evaluation_for(
    *,
    evaluation_id: int,
    attempt_id: int,
    attempt_created_at: datetime,
    bands: dict[str, str],
) -> tuple[WritingEvaluation, WritingAttempt]:
    evaluation = WritingEvaluation(
        id=evaluation_id,
        attempt_id=attempt_id,
        task_response_band=Decimal(bands["task_response"]),
        coherence_and_cohesion_band=Decimal(bands["coherence_and_cohesion"]),
        lexical_resource_band=Decimal(bands["lexical_resource"]),
        grammatical_range_and_accuracy_band=Decimal(
            bands["grammatical_range_and_accuracy"]
        ),
        product_band=Decimal("6.5"),
        criteria_feedback={},
        strengths=[],
        weaknesses=[],
        error_tags=[],
        recommended_skills=[],
        feedback="f",
        provider="deepseek",
        model="deepseek-chat",
        prompt_version="writing-v2",
        rubric_version="writing-task2-v1",
        scoring_policy_version="writing-scoring-v1",
        thinking_mode="disabled",
        created_at=T2,
    )
    attempt = WritingAttempt(
        id=attempt_id,
        question="Q",
        essay="E",
        word_count=1,
        created_at=attempt_created_at,
    )
    return evaluation, attempt


def extract_set(
    *,
    evaluation_id: int,
    attempt_id: int,
    attempt_created_at: datetime,
    bands: dict[str, str],
) -> ExtractedWritingEvidenceSet:
    evaluation, attempt = evaluation_for(
        evaluation_id=evaluation_id,
        attempt_id=attempt_id,
        attempt_created_at=attempt_created_at,
        bands=bands,
    )
    return extract_writing_evidence(evaluation, attempt)


def set_items(
    evidence_set: ExtractedWritingEvidenceSet,
) -> list[ExtractedWritingEvidence]:
    return [getattr(evidence_set, skill) for skill in WRITING_SKILLS]


# ---------------------------------------------------------------------------
# Core EWMA math and single quantization
# ---------------------------------------------------------------------------


def test_ewma_exact_intermediates_never_rounded() -> None:
    assert ewma_estimate([Decimal("6.0")]) == Decimal("6.0")
    assert ewma_estimate([Decimal("6.0"), Decimal("6.5")]) == Decimal("6.25")
    assert ewma_estimate([Decimal("6.0"), Decimal("6.5"), Decimal("7.0")]) == Decimal(
        "6.625"
    )
    assert ewma_estimate(
        [Decimal("6.0"), Decimal("6.5"), Decimal("7.0"), Decimal("6.5")]
    ) == Decimal("6.5625")


def test_quantize_half_up() -> None:
    assert quantize_materialized(Decimal("6.625")) == Decimal("6.63")
    assert quantize_materialized(Decimal("6.375")) == Decimal("6.38")
    assert quantize_materialized(Decimal("6.5625")) == Decimal("6.56")


# ---------------------------------------------------------------------------
# Every P3-02 required example
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bands", "expected"),
    [
        (["6.5"], "6.50"),  # A. first evidence
        (["6.5", "6.5", "6.5"], "6.50"),  # B. repeated equal evidence
        (["6.0", "6.5", "7.0"], "6.63"),  # C. improving sequence
        (["7.0", "6.5", "6.0"], "6.38"),  # D. declining sequence
        (["6.0", "6.5", "7.0", "6.5"], "6.56"),  # E. mixed sequence
        (["0.0"], "0.00"),  # F. lower bound
        (["9.0"], "9.00"),  # G. upper bound
    ],
)
def test_policy_examples(bands: list[str], expected: str) -> None:
    items = [
        item(
            "task_response",
            band,
            evaluation_id=idx + 1,
            source_created_at=T1,
            source_attempt_id=idx + 1,
        )
        for idx, band in enumerate(bands)
    ]
    state = rebuild_skill_state(items, skill="task_response")
    assert state.estimated_band == Decimal(expected)
    assert state.evidence_count == len(bands)
    assert state.last_evidence_writing_evaluation_id == len(bands)


def test_canonical_order_independence_example() -> None:
    a = item(
        "task_response", "6.0", evaluation_id=1, source_created_at=T1, source_attempt_id=1
    )
    b = item(
        "task_response", "7.0", evaluation_id=2, source_created_at=T2, source_attempt_id=2
    )

    forward = rebuild_skill_state([a, b], skill="task_response")
    reverse = rebuild_skill_state([b, a], skill="task_response")

    assert forward == reverse == MaterializedSkillState(
        skill="task_response",
        estimated_band=Decimal("6.50"),
        evidence_count=2,
        last_evidence_writing_evaluation_id=2,
    )


def test_no_evidence_is_unobserved() -> None:
    state = rebuild_skill_state([], skill="task_response")
    assert state == MaterializedSkillState(
        skill="task_response",
        estimated_band=None,
        evidence_count=0,
        last_evidence_writing_evaluation_id=None,
    )
    assert not state.observed


def test_same_created_at_tie_break_by_attempt_id() -> None:
    old = item(
        "task_response", "6.0", evaluation_id=100, source_created_at=T1, source_attempt_id=100
    )
    new = item(
        "task_response", "7.0", evaluation_id=101, source_created_at=T1, source_attempt_id=101
    )
    state = rebuild_skill_state([new, old], skill="task_response")
    # Canonical order must be attempt 100 then 101; last evidence is 101.
    assert state.last_evidence_writing_evaluation_id == 101


# ---------------------------------------------------------------------------
# Arrival-order independence and late older evidence
# ---------------------------------------------------------------------------


def test_late_older_evidence_rebuilds_to_canonical_order() -> None:
    # Canonical source order: A (T1) then B (T2).
    a = item("task_response", "6.0", evaluation_id=1, source_created_at=T1, source_attempt_id=1)
    b = item("task_response", "7.0", evaluation_id=2, source_created_at=T2, source_attempt_id=2)

    applied_a_then_b = rebuild_skill_state([a, b], skill="task_response")
    # B applied first, then late older A arrives: full accepted set is {A, B}.
    late_b_then_a = rebuild_skill_state([b, a], skill="task_response")

    assert applied_a_then_b == late_b_then_a
    assert applied_a_then_b.estimated_band == Decimal("6.50")


def test_repeated_runs_are_deterministic() -> None:
    items = [
        item("lexical_resource", band, evaluation_id=i, source_created_at=T1, source_attempt_id=i)
        for i, band in enumerate(["6.0", "6.5", "7.0"], start=1)
    ]
    assert rebuild_skill_state(items, skill="lexical_resource") == rebuild_skill_state(
        items, skill="lexical_resource"
    )


# ---------------------------------------------------------------------------
# Four-skill rebuild
# ---------------------------------------------------------------------------


def test_rebuild_all_skills_tracks_independent_sequences() -> None:
    first = extract_set(
        evaluation_id=1,
        attempt_id=1,
        attempt_created_at=T1,
        bands={
            "task_response": "6.0",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.0",
            "grammatical_range_and_accuracy": "6.5",
        },
    )
    second = extract_set(
        evaluation_id=2,
        attempt_id=2,
        attempt_created_at=T2,
        bands={
            "task_response": "6.5",
            "coherence_and_cohesion": "6.5",
            "lexical_resource": "6.5",
            "grammatical_range_and_accuracy": "6.0",
        },
    )
    states = rebuild_all_skill_states(set_items(first) + set_items(second))

    assert states["task_response"].estimated_band == Decimal("6.25")
    assert states["coherence_and_cohesion"].estimated_band == Decimal("6.50")
    assert states["lexical_resource"].estimated_band == Decimal("6.25")
    assert states["grammatical_range_and_accuracy"].estimated_band == Decimal("6.25")
    assert all(state.evidence_count == 2 for state in states.values())


def test_rebuild_all_unobserved_when_no_evidence() -> None:
    states = rebuild_all_skill_states([])
    assert set(states) == set(WRITING_SKILLS)
    assert all(not state.observed for state in states.values())


def test_per_skill_count_independent_of_other_skills() -> None:
    tr_items = [
        item("task_response", band, evaluation_id=i, source_created_at=T1, source_attempt_id=i)
        for i, band in enumerate(["6.0", "6.5"], start=1)
    ]
    cc_items = [
        item(
            "coherence_and_cohesion",
            "6.5",
            evaluation_id=i,
            source_created_at=T1,
            source_attempt_id=i,
        )
        for i in (1, 2, 3)
    ]
    states = rebuild_all_skill_states(tr_items + cc_items)
    assert states["task_response"].evidence_count == 2
    assert states["coherence_and_cohesion"].evidence_count == 3
    assert states["lexical_resource"].evidence_count == 0
    assert states["grammatical_range_and_accuracy"].evidence_count == 0


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_unsupported_policy_version_rejected() -> None:
    with pytest.raises(WritingStateReplayError, match="unsupported"):
        require_state_policy_version("writing-state-ewma-v2")


def test_frozen_policy_version_accepted() -> None:
    require_state_policy_version("writing-state-ewma-v1")


def test_duplicate_canonical_evidence_is_invariant_violation() -> None:
    dup = [
        item("task_response", "6.0", evaluation_id=1, source_created_at=T1, source_attempt_id=1),
        item("task_response", "6.5", evaluation_id=1, source_created_at=T1, source_attempt_id=1),
    ]
    with pytest.raises(WritingStateReplayError, match="duplicate"):
        rebuild_skill_state(dup, skill="task_response")


def test_empty_ewma_rejected() -> None:
    with pytest.raises(WritingStateReplayError, match="empty"):
        ewma_estimate([])
