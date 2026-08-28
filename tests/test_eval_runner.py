"""P10-12 bounded runner mode-separation and fail-closed tests."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.eval.attribution import FindingEvidence
from app.eval.calibration import CalibrationSample
from app.eval.corpora import CalibrationCorpus, load_calibration_corpus, load_regression_corpus
from app.eval.runner import EvalRunner, LiveCalibrationExecution, ProviderExecutionMetadata
from app.eval.schemas import (
    CalibrationCase,
    EvalFinding,
    EvalMode,
    EvalSeverity,
    EvalStatus,
    ProviderCapture,
)
from app.schemas.common import BandScore
from app.schemas.writing import CriterionBandScores


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "eval"


def _passing_executor(case):
    return tuple(
        FindingEvidence(
            finding=EvalFinding(
                evaluator=evaluator,
                status=EvalStatus.PASS,
                severity=EvalSeverity.INFO,
            )
        )
        for evaluator in case.applicable_evaluators
    )


def _calibration_case() -> CalibrationCase:
    return CalibrationCase.model_validate(
        {
            "case_id": "runner-calibration",
            "question": "Discuss both views and give your opinion.",
            "essay": "Synthetic runner test input, not canonical calibration evidence.",
            "reference_labels": [
                {
                    "rater_id": "synthetic-rater",
                    "criteria": {criterion: {"value": "6.0"} for criterion in (
                        "task_response",
                        "coherence_and_cohesion",
                        "lexical_resource",
                        "grammatical_range_and_accuracy",
                    )},
                    "overall_band": {"value": "6.0"},
                    "provenance": {"source": "unit-test", "locator": "test_eval_runner"},
                }
            ],
            "reference_tier": "b",
            "provenance": {"source": "unit-test", "locator": "test_eval_runner"},
            "ambiguity": "unambiguous",
        }
    )


def _criteria() -> CriterionBandScores:
    return CriterionBandScores.model_validate(
        {criterion: {"value": "6.0"} for criterion in (
            "task_response",
            "coherence_and_cohesion",
            "lexical_resource",
            "grammatical_range_and_accuracy",
        )}
    )


def test_deterministic_runner_orders_cases_and_executes_all_applicable_evaluators() -> None:
    corpus = load_regression_corpus(
        FIXTURE_ROOT / "regression_corpus.json",
        fixture_directory=FIXTURE_ROOT,
    )
    executors = {case.case_id: _passing_executor for case in corpus.cases}
    result = EvalRunner().run_deterministic(
        run_id="deterministic-run",
        corpus=corpus,
        executors=executors,
    )

    assert result.mode is EvalMode.DETERMINISTIC_REGRESSION
    assert result.status is EvalStatus.PASS
    assert tuple(item.case_id for item in result.cases) == tuple(
        sorted(case.case_id for case in corpus.cases)
    )
    assert all(item.attribution is not None for item in result.cases)


def test_unregistered_or_failed_case_does_not_corrupt_following_cases() -> None:
    corpus = load_regression_corpus(
        FIXTURE_ROOT / "regression_corpus.json",
        fixture_directory=FIXTURE_ROOT,
    )
    ordered = sorted(corpus.cases, key=lambda case: case.case_id)
    executors = {case.case_id: _passing_executor for case in ordered[1:]}
    result = EvalRunner().run_deterministic(
        run_id="isolated-run",
        corpus=corpus,
        executors=executors,
    )

    assert result.status is EvalStatus.INVALID_CASE
    assert result.cases[0].status is EvalStatus.INVALID_CASE
    assert all(item.status is EvalStatus.PASS for item in result.cases[1:])


def test_canonical_empty_calibration_corpus_blocks_without_provider_call() -> None:
    corpus = load_calibration_corpus(FIXTURE_ROOT / "calibration_corpus.json")
    calls = 0

    def provider(case):
        nonlocal calls
        calls += 1
        raise AssertionError("provider must not run without admissible references")

    result = EvalRunner().run_live_calibration(
        run_id="live-empty",
        corpus=corpus,
        provider=provider,
    )

    assert result.status is EvalStatus.BLOCKED
    assert result.blocked_reason == "insufficient_reference_data"
    assert calls == 0


def test_live_calibration_requires_injected_provider_and_records_metadata() -> None:
    case = _calibration_case()
    corpus = CalibrationCorpus(reference_data_status="available", cases=(case,))
    blocked = EvalRunner().run_live_calibration(
        run_id="live-no-provider",
        corpus=corpus,
        provider=None,
    )
    assert blocked.status is EvalStatus.BLOCKED

    def provider(selected: CalibrationCase) -> LiveCalibrationExecution:
        return LiveCalibrationExecution(
            sample=CalibrationSample(
                case=selected,
                mode=EvalMode.LIVE_CALIBRATION,
                application_criteria=_criteria(),
                application_overall_band=BandScore(value=Decimal("6.0")),
            ),
            provider_metadata=ProviderExecutionMetadata(
                provider="injected-provider",
                model="injected-model",
                prompt_version="writing-task2-prompt-v1",
                rubric_version="writing-task2-v1",
                scoring_policy_version="writing-task2-v1",
                run_config_version="test-run-v1",
            ),
        )

    result = EvalRunner().run_live_calibration(
        run_id="live-injected",
        corpus=corpus,
        provider=provider,
    )
    assert result.status is EvalStatus.PASS
    assert result.cases[0].provider_metadata.provider == "injected-provider"


def test_calibration_replay_consumes_capture_without_provider() -> None:
    case = _calibration_case()
    corpus = CalibrationCorpus(reference_data_status="available", cases=(case,))
    capture = ProviderCapture.model_validate(
        {
            "capture_id": "runner-capture",
            "case_id": case.case_id,
            "provider": "captured-provider",
            "model": "captured-model",
            "thinking_mode": "disabled",
            "prompt_version": "writing-task2-prompt-v1",
            "rubric_version": "writing-task2-v1",
            "scoring_policy_version": "writing-task2-v1",
            "provider_structured_payload": {"criteria": "captured"},
            "application_normalized_result": {
                "criteria": _criteria().model_dump(mode="json"),
                "product_band": "6.0",
            },
            "capture_timestamp": datetime(2026, 1, 1, tzinfo=UTC),
            "run_config_version": "capture-run-v1",
        }
    )

    result = EvalRunner().run_calibration_replay(
        run_id="replay-run",
        corpus=corpus,
        captures=(capture,),
    )

    assert result.status is EvalStatus.PASS
    assert result.cases[0].provider_capture_id == capture.capture_id
    assert result.cases[0].provider_metadata.provider == capture.provider


def test_runner_rejects_unbounded_case_selection() -> None:
    corpus = load_regression_corpus(
        FIXTURE_ROOT / "regression_corpus.json",
        fixture_directory=FIXTURE_ROOT,
    )
    try:
        EvalRunner(max_cases=1).run_deterministic(
            run_id="bounded-run",
            corpus=corpus,
            executors={case.case_id: _passing_executor for case in corpus.cases},
        )
    except ValueError as error:
        assert str(error) == "selected case count exceeds runner bound"
    else:
        raise AssertionError("runner accepted an unbounded case selection")


def test_runner_rejects_empty_or_unknown_selection_without_fabricating_pass() -> None:
    corpus = load_regression_corpus(
        FIXTURE_ROOT / "regression_corpus.json",
        fixture_directory=FIXTURE_ROOT,
    )
    result = EvalRunner().run_deterministic(
        run_id="empty-selection",
        corpus=corpus,
        executors={},
        selected_case_ids=frozenset({"not-a-canonical-case"}),
    )

    assert result.status is EvalStatus.INVALID_CASE
    assert result.blocked_reason == "no_cases_selected"