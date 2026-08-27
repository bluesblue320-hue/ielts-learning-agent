"""P10-10 deterministic calibration mathematics and data-gap behavior."""

from datetime import UTC, datetime
from decimal import Decimal

from app.eval.calibration import (
    CalibrationSample,
    analyze_calibration,
    sample_from_provider_capture,
)
from app.eval.schemas import CalibrationCase, EvalMode, ProviderCapture
from app.schemas.common import BandScore
from app.schemas.writing import CriterionBandScores


def _criteria(tr: str, cc: str, lr: str, gra: str) -> CriterionBandScores:
    return CriterionBandScores.model_validate(
        {
            "task_response": {"value": tr},
            "coherence_and_cohesion": {"value": cc},
            "lexical_resource": {"value": lr},
            "grammatical_range_and_accuracy": {"value": gra},
        }
    )


def _case(
    case_id: str,
    *,
    ambiguity: str = "unambiguous",
    ratings: tuple[CriterionBandScores, ...] | None = None,
    tier: str = "b",
) -> CalibrationCase:
    ratings = ratings or (_criteria("6.0", "6.0", "6.0", "6.0"),)
    return CalibrationCase.model_validate(
        {
            "case_id": case_id,
            "question": "Discuss both views and give your opinion.",
            "essay": "Synthetic unit-test input; it is not canonical reference evidence.",
            "reference_labels": [
                {
                    "rater_id": f"rater-{index}",
                    "criteria": rating.model_dump(),
                    "overall_band": {"value": "6.0"},
                    "provenance": {
                        "source": "synthetic-unit-test",
                        "locator": f"tests/test_eval_calibration.py::{case_id}:{index}",
                    },
                }
                for index, rating in enumerate(ratings, start=1)
            ],
            "reference_tier": tier,
            "provenance": {
                "source": "synthetic-unit-test",
                "locator": f"tests/test_eval_calibration.py::{case_id}",
            },
            "ambiguity": ambiguity,
        }
    )


def _sample(case: CalibrationCase, criteria: CriterionBandScores) -> CalibrationSample:
    return CalibrationSample(
        case=case,
        mode=EvalMode.CALIBRATION_REPLAY,
        application_criteria=criteria,
        application_overall_band=BandScore(value=Decimal("6.5")),
        provider_capture_id="capture-unit-test",
    )


def test_zero_eligible_samples_are_truthfully_blocked() -> None:
    result = analyze_calibration(())

    assert result.status.value == "blocked"
    assert result.eligible_sample_count == 0
    assert result.blocked_reason == "insufficient_reference_data"
    assert result.overall.mean_absolute_error is None


def test_calibration_metrics_use_exact_decimal_math_and_tiers() -> None:
    case = _case("calibration-math")
    result = analyze_calibration(
        (_sample(case, _criteria("6.0", "6.5", "7.0", "5.5")),)
    )

    assert result.status.value == "pass"
    assert result.eligible_sample_count == 1
    assert result.overall.mean_absolute_error == Decimal("0.5")
    assert result.overall.signed_bias == Decimal("0.5")
    assert result.by_criterion["task_response"].exact_agreement == Decimal("1")
    assert result.by_criterion["lexical_resource"].mean_absolute_error == Decimal("1.0")
    assert result.by_evidence_tier[case.reference_tier].sample_count == 4


def test_ambiguous_case_is_excluded_but_human_disagreement_is_preserved() -> None:
    case = _case(
        "human-disagreement",
        ambiguity="rater_disagreement",
        ratings=(
            _criteria("6.0", "6.0", "6.0", "6.0"),
            _criteria("6.5", "6.0", "7.0", "5.5"),
        ),
    )
    result = analyze_calibration((_sample(case, _criteria("6.5", "6.5", "6.5", "6.5")),))

    assert result.status.value == "blocked"
    assert result.excluded_sample_count == 1
    assert result.ambiguous_sample_count == 1
    assert result.human_disagreement.comparison_count == 4
    assert result.human_disagreement.within_half_band == Decimal("0.75")
    assert result.human_disagreement.criterion_mean_absolute_difference["lexical_resource"] == Decimal("1.0")


def test_provider_capture_replay_uses_application_normalized_result() -> None:
    case = _case("captured-replay")
    capture = ProviderCapture.model_validate(
        {
            "capture_id": "capture-replay",
            "case_id": case.case_id,
            "provider": "captured-provider",
            "model": "captured-model",
            "thinking_mode": "disabled",
            "prompt_version": "writing-task2-prompt-v1",
            "rubric_version": "writing-task2-v1",
            "scoring_policy_version": "writing-task2-v1",
            "provider_structured_payload": {"criteria": "captured"},
            "application_normalized_result": {
                "criteria": _criteria("6.0", "6.0", "6.0", "6.0").model_dump(mode="json"),
                "product_band": "6.0",
            },
            "capture_timestamp": datetime(2026, 1, 1, tzinfo=UTC),
            "run_config_version": "run-v1",
        }
    )

    sample = sample_from_provider_capture(case, capture)
    result = analyze_calibration((sample,))

    assert sample.provider_capture_id == capture.capture_id
    assert result.status.value == "pass"
    assert result.overall.exact_agreement == Decimal("1")
