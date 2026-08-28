"""P10-13 structured and human report derivation tests."""

from app.eval.attribution import FindingEvidence, attribute_findings
from app.eval.reporting import build_structured_report, render_human_report
from app.eval.runner import RunnerCaseResult, RunnerSuiteResult
from app.eval.schemas import (
    CALIBRATION_CORPUS_VERSION,
    REGRESSION_CORPUS_VERSION,
    EvalFinding,
    EvalMode,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)


def _failed_suite() -> RunnerSuiteResult:
    finding = EvalFinding(
        evaluator=EvaluatorId.AUTHORITY,
        status=EvalStatus.FAIL,
        severity=EvalSeverity.VETO,
        first_failing_boundary=FailureBoundary.AUTHORITY,
        failure_codes=("authority_bypass",),
    )
    attribution = attribute_findings(
        mode=EvalMode.DETERMINISTIC_REGRESSION,
        evidence=(FindingEvidence(finding=finding),),
    )
    return RunnerSuiteResult(
        run_id="report-run",
        mode=EvalMode.DETERMINISTIC_REGRESSION,
        corpus_version=REGRESSION_CORPUS_VERSION,
        cases=(
            RunnerCaseResult(
                case_id="authority-case",
                mode=EvalMode.DETERMINISTIC_REGRESSION,
                status=EvalStatus.FAIL,
                findings=(finding,),
                attribution=attribution,
            ),
        ),
        status=EvalStatus.FAIL,
    )


def test_machine_report_preserves_versions_status_veto_and_first_failure() -> None:
    report = build_structured_report(
        _failed_suite(),
        config_version="phase10-test-config-v1",
    )

    assert report.report_version == "writing-eval-report-v1"
    assert report.cases[0].result_schema_version == "writing-eval-result-v1"
    assert report.summary.status_counts[EvalStatus.FAIL] == 1
    assert report.summary.veto_failure_count == 1
    assert report.cases[0].first_failing_boundary is FailureBoundary.AUTHORITY
    assert report.cases[0].failure_codes == ("authority_bypass",)


def test_human_report_is_stable_and_derived_from_structured_result() -> None:
    report = build_structured_report(
        _failed_suite(),
        config_version="phase10-test-config-v1",
    )

    first = render_human_report(report)
    second = render_human_report(report)

    assert first == second
    assert "VETO failures: 1" in first
    assert "`authority`: 1" in first
    assert "Provider variance != code regression" in first
    assert "private" not in first.lower()


def test_empty_calibration_report_truthfully_exposes_reference_limit() -> None:
    suite = RunnerSuiteResult(
        run_id="calibration-empty",
        mode=EvalMode.CALIBRATION_REPLAY,
        corpus_version=CALIBRATION_CORPUS_VERSION,
        status=EvalStatus.BLOCKED,
        blocked_reason="insufficient_reference_data",
    )
    report = build_structured_report(
        suite,
        config_version="phase10-test-config-v1",
    )
    human = render_human_report(report)

    assert report.suite_status is EvalStatus.BLOCKED
    assert report.summary.case_count == 0
    assert "zero admissible reference samples" in human
    assert "not a fresh provider run" in human


def test_structured_report_contains_no_submission_or_essay_payload_fields() -> None:
    payload = build_structured_report(
        _failed_suite(),
        config_version="phase10-test-config-v1",
    ).model_dump(mode="json")
    serialized = str(payload).lower()

    assert "essay" not in serialized
    assert "api_key" not in serialized
    assert "database_url" not in serialized
    assert "chain_of_thought" not in serialized
