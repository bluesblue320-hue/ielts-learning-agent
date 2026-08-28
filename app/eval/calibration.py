"""Deterministic score-calibration analysis for Phase 10."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from itertools import combinations
from typing import Literal

from pydantic import Field

from app.eval.schemas import (
    AmbiguityState,
    CalibrationCase,
    EvalMode,
    EvalSchema,
    EvalStatus,
    ProviderCapture,
    ReferenceTier,
)
from app.schemas.common import BandScore
from app.schemas.writing import CriterionBandScores


CRITERIA = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)
PRIMARY_EXCLUSIONS = {
    AmbiguityState.RATER_DISAGREEMENT,
    AmbiguityState.INSUFFICIENT_REFERENCE,
    AmbiguityState.ADJUDICATION_PENDING,
    AmbiguityState.EXCLUDED_FROM_PRIMARY_METRIC,
}


class CalibrationSample(EvalSchema):
    """One application-normalized result paired with immutable references."""

    case: CalibrationCase
    mode: Literal[EvalMode.LIVE_CALIBRATION, EvalMode.CALIBRATION_REPLAY]
    application_criteria: CriterionBandScores
    application_overall_band: BandScore | None = None
    provider_capture_id: str | None = None


class AgreementMetrics(EvalSchema):
    sample_count: int = Field(ge=0)
    exact_agreement: Decimal | None = None
    within_half_band: Decimal | None = None
    within_one_band: Decimal | None = None
    mean_absolute_error: Decimal | None = None
    signed_bias: Decimal | None = None
    system_distribution: dict[str, int] = Field(default_factory=dict)
    reference_distribution: dict[str, int] = Field(default_factory=dict)


class HumanDisagreementMetrics(EvalSchema):
    comparison_count: int = Field(ge=0)
    exact_agreement: Decimal | None = None
    within_half_band: Decimal | None = None
    mean_absolute_rater_difference: Decimal | None = None
    criterion_mean_absolute_difference: dict[str, Decimal] = Field(default_factory=dict)


class CalibrationAnalysis(EvalSchema):
    status: EvalStatus
    eligible_sample_count: int = Field(ge=0)
    excluded_sample_count: int = Field(ge=0)
    ambiguous_sample_count: int = Field(ge=0)
    overall: AgreementMetrics
    by_criterion: dict[str, AgreementMetrics]
    by_evidence_tier: dict[ReferenceTier, AgreementMetrics]
    human_disagreement: HumanDisagreementMetrics
    blocked_reason: str | None = None


def sample_from_provider_capture(
    case: CalibrationCase,
    capture: ProviderCapture,
) -> CalibrationSample:
    """Create replay input from the capture's application-normalized result."""

    if capture.case_id != case.case_id:
        raise ValueError("Provider capture case identity does not match calibration case.")
    normalized = capture.application_normalized_result
    criteria = normalized.get("criteria")
    overall = normalized.get("product_band")
    if not isinstance(criteria, dict):
        raise ValueError("Provider capture requires normalized criterion scores.")
    return CalibrationSample(
        case=case,
        mode=EvalMode.CALIBRATION_REPLAY,
        application_criteria=CriterionBandScores.model_validate(criteria),
        application_overall_band=(
            BandScore.model_validate({"value": overall}) if overall is not None else None
        ),
        provider_capture_id=capture.capture_id,
    )


def analyze_calibration(samples: tuple[CalibrationSample, ...]) -> CalibrationAnalysis:
    """Compute exact Decimal metrics without changing scoring or reference truth."""

    eligible: list[tuple[CalibrationSample, CriterionBandScores, BandScore | None]] = []
    excluded = 0
    ambiguous = 0
    for sample in samples:
        case = sample.case
        if case.ambiguity is not AmbiguityState.UNAMBIGUOUS:
            ambiguous += 1
        reference = _primary_reference(case)
        if reference is None:
            excluded += 1
            continue
        eligible.append((sample, reference[0], reference[1]))

    human = _human_disagreement(samples)
    if not eligible:
        return CalibrationAnalysis(
            status=EvalStatus.BLOCKED,
            eligible_sample_count=0,
            excluded_sample_count=excluded,
            ambiguous_sample_count=ambiguous,
            overall=_agreement(()),
            by_criterion={criterion: _agreement(()) for criterion in CRITERIA},
            by_evidence_tier={},
            human_disagreement=human,
            blocked_reason="insufficient_reference_data",
        )

    criterion_pairs = {
        criterion: tuple(
            (
                getattr(sample.application_criteria, criterion).value,
                getattr(reference, criterion).value,
            )
            for sample, reference, _ in eligible
        )
        for criterion in CRITERIA
    }
    overall_pairs = tuple(
        (sample.application_overall_band.value, reference_overall.value)
        for sample, _, reference_overall in eligible
        if sample.application_overall_band is not None and reference_overall is not None
    )
    by_tier = {
        tier: _agreement(
            tuple(
                pair
                for sample, reference, _ in eligible
                if sample.case.reference_tier is tier
                for criterion in CRITERIA
                for pair in ((
                    getattr(sample.application_criteria, criterion).value,
                    getattr(reference, criterion).value,
                ),)
            )
        )
        for tier in ReferenceTier
        if any(sample.case.reference_tier is tier for sample, _, _ in eligible)
    }
    return CalibrationAnalysis(
        status=EvalStatus.PASS,
        eligible_sample_count=len(eligible),
        excluded_sample_count=excluded,
        ambiguous_sample_count=ambiguous,
        overall=_agreement(overall_pairs),
        by_criterion={
            criterion: _agreement(pairs) for criterion, pairs in criterion_pairs.items()
        },
        by_evidence_tier=by_tier,
        human_disagreement=human,
    )


def _primary_reference(
    case: CalibrationCase,
) -> tuple[CriterionBandScores, BandScore | None] | None:
    if case.adjudication is not None:
        return case.adjudication.criteria, case.adjudication.overall_band
    if case.ambiguity in PRIMARY_EXCLUSIONS:
        return None
    first = case.reference_labels[0]
    if len(case.reference_labels) == 1:
        return first.criteria, first.overall_band
    if all(
        label.criteria == first.criteria and label.overall_band == first.overall_band
        for label in case.reference_labels[1:]
    ):
        return first.criteria, first.overall_band
    return None


def _agreement(pairs: tuple[tuple[Decimal, Decimal], ...]) -> AgreementMetrics:
    if not pairs:
        return AgreementMetrics(sample_count=0)
    deltas = tuple(system - reference for system, reference in pairs)
    count = Decimal(len(deltas))
    return AgreementMetrics(
        sample_count=len(deltas),
        exact_agreement=Decimal(sum(delta == 0 for delta in deltas)) / count,
        within_half_band=Decimal(sum(abs(delta) <= Decimal("0.5") for delta in deltas)) / count,
        within_one_band=Decimal(sum(abs(delta) <= Decimal("1.0") for delta in deltas)) / count,
        mean_absolute_error=sum((abs(delta) for delta in deltas), Decimal("0")) / count,
        signed_bias=sum(deltas, Decimal("0")) / count,
        system_distribution=_distribution(system for system, _ in pairs),
        reference_distribution=_distribution(reference for _, reference in pairs),
    )


def _distribution(values) -> dict[str, int]:
    counts = Counter(f"{value:.1f}" for value in values)
    return dict(sorted(counts.items(), key=lambda item: Decimal(item[0])))


def _human_disagreement(samples: tuple[CalibrationSample, ...]) -> HumanDisagreementMetrics:
    all_pairs: list[tuple[Decimal, Decimal]] = []
    criterion_pairs: dict[str, list[tuple[Decimal, Decimal]]] = {
        criterion: [] for criterion in CRITERIA
    }
    for sample in samples:
        for left, right in combinations(sample.case.reference_labels, 2):
            for criterion in CRITERIA:
                pair = (
                    getattr(left.criteria, criterion).value,
                    getattr(right.criteria, criterion).value,
                )
                all_pairs.append(pair)
                criterion_pairs[criterion].append(pair)
    if not all_pairs:
        return HumanDisagreementMetrics(comparison_count=0)
    metrics = _agreement(tuple(all_pairs))
    return HumanDisagreementMetrics(
        comparison_count=len(all_pairs),
        exact_agreement=metrics.exact_agreement,
        within_half_band=metrics.within_half_band,
        mean_absolute_rater_difference=metrics.mean_absolute_error,
        criterion_mean_absolute_difference={
            criterion: _agreement(tuple(pairs)).mean_absolute_error
            for criterion, pairs in criterion_pairs.items()
            if pairs
        },
    )


__all__ = [
    "AgreementMetrics",
    "CalibrationAnalysis",
    "CalibrationSample",
    "HumanDisagreementMetrics",
    "analyze_calibration",
    "sample_from_provider_capture",
]
