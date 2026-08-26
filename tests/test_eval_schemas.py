"""Focused deterministic coverage for the frozen P10-03 Eval contracts."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.eval.schemas import (
    AmbiguityState,
    CalibrationCase,
    EvalCategory,
    EvalFinding,
    EvalMode,
    EvalResult,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
    ProviderCapture,
    ProvenanceReference,
    RawReferenceRating,
    ReferenceTier,
    RegressionCase,
    SeverityExpectation,
)


def _criteria(band: str = "6.0") -> dict[str, dict[str, str]]:
    return {
        "task_response": {"value": band},
        "coherence_and_cohesion": {"value": band},
        "lexical_resource": {"value": band},
        "grammatical_range_and_accuracy": {"value": band},
    }


def _provenance() -> ProvenanceReference:
    return ProvenanceReference(source="repository-test", locator="tests/example")


def _regression_case(**overrides: object) -> RegressionCase:
    values: dict[str, object] = {
        "case_id": "provider-contract-invalid-payload",
        "description": "Malformed provider payload fails closed.",
        "category": EvalCategory.PROVIDER_CONTRACT,
        "input": {"submission": "canonical"},
        "provider_fixture": "invalid-payload.json",
        "expected_structured_outcomes": {"status": "provider_error"},
        "applicable_evaluators": (EvaluatorId.OUTCOME, EvaluatorId.AUTHORITY),
        "severity_expectations": (
            SeverityExpectation(
                boundary=FailureBoundary.PROVIDER_CONTRACT,
                severity=EvalSeverity.VETO,
            ),
        ),
        "provenance": _provenance(),
    }
    values.update(overrides)
    return RegressionCase.model_validate(values)


def _raw_rating(rater_id: str = "rater-a") -> RawReferenceRating:
    return RawReferenceRating.model_validate(
        {
            "rater_id": rater_id,
            "criteria": _criteria(),
            "overall_band": {"value": "6.0"},
            "provenance": _provenance(),
        }
    )


def test_regression_case_uses_frozen_versions_and_strict_enums() -> None:
    case = _regression_case()

    assert case.schema_version == "writing-eval-regression-case-v1"
    assert case.corpus_version == "writing-eval-regression-corpus-v1"
    assert case.mode == EvalMode.DETERMINISTIC_REGRESSION

    with pytest.raises(ValidationError, match="category"):
        _regression_case(category="unknown")


def test_regression_case_rejects_extra_fields_and_two_fixture_kinds() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _regression_case(unexpected="no")
    with pytest.raises(ValidationError, match="not both"):
        _regression_case(captured_fixture_reference="capture-1")


def test_calibration_case_preserves_raw_ratings_and_validates_half_bands() -> None:
    case = CalibrationCase.model_validate(
        {
            "case_id": "admissible-reference-example",
            "question": "Discuss both views and give your opinion.",
            "essay": "This is a deliberately short repository-only example essay.",
            "reference_labels": [_raw_rating().model_dump()],
            "reference_tier": ReferenceTier.B,
            "provenance": _provenance().model_dump(),
            "ambiguity": AmbiguityState.UNAMBIGUOUS,
        }
    )

    assert case.reference_labels[0].rater_id == "rater-a"
    with pytest.raises(ValidationError):
        RawReferenceRating.model_validate(
            {
                "rater_id": "rater-invalid-band",
                "criteria": _criteria("6.3"),
                "provenance": _provenance().model_dump(),
            }
        )


def test_calibration_case_rejects_duplicate_raw_rater_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate raw rater IDs"):
        CalibrationCase.model_validate(
            {
                "case_id": "duplicate-rater",
                "question": "Discuss both views and give your opinion.",
                "essay": "A repository-only example essay for strict validation.",
                "reference_labels": [
                    _raw_rating("rater-a").model_dump(),
                    _raw_rating("rater-a").model_dump(),
                ],
                "reference_tier": "b",
                "provenance": _provenance().model_dump(),
                "ambiguity": "rater_disagreement",
            }
        )


def test_provider_capture_rejects_secret_and_chain_of_thought_fields() -> None:
    base = {
        "capture_id": "capture-example",
        "case_id": "admissible-reference-example",
        "provider": "recorded-provider",
        "model": "recorded-model",
        "thinking_mode": "disabled",
        "prompt_version": "writing-task2-prompt-v1",
        "rubric_version": "writing-task2-v1",
        "scoring_policy_version": "writing-task2-v1",
        "provider_structured_payload": {"criteria": "captured"},
        "application_normalized_result": {"product_band": "6.0"},
        "capture_timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "run_config_version": "run-v1",
    }
    assert ProviderCapture.model_validate(base).capture_id == "capture-example"

    with pytest.raises(ValidationError, match="forbidden field"):
        ProviderCapture.model_validate(
            {**base, "provider_structured_payload": {"chain_of_thought": "never"}}
        )


def test_result_preserves_veto_and_first_failure_without_blending() -> None:
    result = EvalResult(
        run_id="run-1",
        case_id="provider-contract-invalid-payload",
        mode=EvalMode.DETERMINISTIC_REGRESSION,
        findings=(
            EvalFinding(
                evaluator=EvaluatorId.OUTCOME,
                status=EvalStatus.PASS,
                severity=EvalSeverity.INFO,
            ),
            EvalFinding(
                evaluator=EvaluatorId.AUTHORITY,
                status=EvalStatus.FAIL,
                severity=EvalSeverity.VETO,
                first_failing_boundary=FailureBoundary.AUTHORITY,
                failure_codes=("fabricated_success",),
            ),
        ),
    )

    assert result.status == EvalStatus.FAIL
    assert result.severity == EvalSeverity.VETO

    with pytest.raises(ValidationError, match="requires its first failing boundary"):
        EvalFinding(
            evaluator=EvaluatorId.OUTCOME,
            status=EvalStatus.FAIL,
            severity=EvalSeverity.MAJOR,
        )
