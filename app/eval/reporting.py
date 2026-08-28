"""Machine-readable and human-readable Phase 10 Eval reporting."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.eval.runner import ProviderExecutionMetadata, RunnerSuiteResult
from app.eval.schemas import (
    CALIBRATION_RESULT_SCHEMA_VERSION,
    EVAL_RESULT_SCHEMA_VERSION,
    POLICY_VERSION,
    REPORT_VERSION,
    EvalFinding,
    EvalMode,
    EvalSchema,
    EvalSeverity,
    EvalStatus,
    FailureBoundary,
)
from app.eval.calibration import CalibrationAnalysis


class ReportCase(EvalSchema):
    case_id: str
    result_schema_version: Literal[
        "writing-eval-result-v1",
        "writing-score-calibration-result-v1",
    ]
    status: EvalStatus
    severity: EvalSeverity
    findings: tuple[EvalFinding, ...] = ()
    first_failing_boundary: FailureBoundary | None = None
    failure_codes: tuple[str, ...] = ()
    calibration: CalibrationAnalysis | None = None
    provider_metadata: ProviderExecutionMetadata | None = None
    provider_capture_id: str | None = None
    blocked_or_invalid_reason: str | None = None


class ReportSummary(EvalSchema):
    case_count: int = Field(ge=0)
    status_counts: dict[EvalStatus, int]
    veto_failure_count: int = Field(ge=0)
    first_failure_counts: dict[FailureBoundary, int]


class StructuredEvalReport(EvalSchema):
    report_version: Literal["writing-eval-report-v1"] = REPORT_VERSION
    policy_version: Literal["writing-eval-calibration-v1"] = POLICY_VERSION
    run_id: str
    mode: EvalMode
    corpus_version: Literal[
        "writing-eval-regression-corpus-v1",
        "writing-score-calibration-corpus-v1",
    ]
    suite_status: EvalStatus
    config_version: str
    generated_at: datetime | None = None
    summary: ReportSummary
    cases: tuple[ReportCase, ...]
    blocked_reason: str | None = None
    known_exclusions: tuple[str, ...] = ()


def build_structured_report(
    suite: RunnerSuiteResult,
    *,
    config_version: str,
    generated_at: datetime | None = None,
    known_exclusions: tuple[str, ...] = (),
) -> StructuredEvalReport:
    """Project runner results into the one report truth model."""

    cases = tuple(_report_case(suite.mode, result) for result in suite.cases)
    status_counts = Counter(case.status for case in cases)
    first_failure_counts = Counter(
        case.first_failing_boundary
        for case in cases
        if case.first_failing_boundary is not None
    )
    veto_count = sum(
        case.severity is EvalSeverity.VETO
        and case.status in {EvalStatus.FAIL, EvalStatus.BLOCKED, EvalStatus.INVALID_CASE}
        for case in cases
    )
    exclusions = list(known_exclusions)
    if suite.blocked_reason == "insufficient_reference_data":
        exclusions.append("canonical calibration corpus has zero admissible reference samples")
    return StructuredEvalReport(
        run_id=suite.run_id,
        mode=suite.mode,
        corpus_version=suite.corpus_version,
        suite_status=suite.status,
        config_version=config_version,
        generated_at=generated_at,
        summary=ReportSummary(
            case_count=len(cases),
            status_counts={status: status_counts.get(status, 0) for status in EvalStatus},
            veto_failure_count=veto_count,
            first_failure_counts=dict(first_failure_counts),
        ),
        cases=cases,
        blocked_reason=suite.blocked_reason,
        known_exclusions=tuple(dict.fromkeys(exclusions)),
    )


def render_human_report(report: StructuredEvalReport) -> str:
    """Render stable Markdown exclusively from the structured report."""

    status_line = ", ".join(
        f"{status.value.upper()}={report.summary.status_counts.get(status, 0)}"
        for status in EvalStatus
    )
    lines = [
        "# Phase 10 Eval Report",
        "",
        f"- Report version: `{report.report_version}`",
        f"- Run: `{report.run_id}`",
        f"- Mode: `{report.mode.value}`",
        f"- Corpus: `{report.corpus_version}`",
        f"- Suite status: `{report.suite_status.value}`",
        f"- Cases: {report.summary.case_count}",
        f"- Status counts: {status_line}",
        f"- VETO failures: {report.summary.veto_failure_count}",
    ]
    if report.blocked_reason:
        lines.append(f"- Blocked reason: `{report.blocked_reason}`")
    lines.extend(["", "## First-failure attribution", ""])
    if report.summary.first_failure_counts:
        lines.extend(
            f"- `{boundary.value}`: {count}"
            for boundary, count in sorted(
                report.summary.first_failure_counts.items(),
                key=lambda item: item[0].value,
            )
        )
    else:
        lines.append("- No failing boundary was recorded.")
    lines.extend(["", "## Cases", ""])
    if report.cases:
        for case in report.cases:
            detail = f"- `{case.case_id}`: `{case.status.value}` / `{case.severity.value}`"
            if case.first_failing_boundary:
                detail += f" at `{case.first_failing_boundary.value}`"
            if case.provider_capture_id:
                detail += f" (replay capture `{case.provider_capture_id}`)"
            lines.append(detail)
    else:
        lines.append("- No eligible cases executed.")
    lines.extend(["", "## Calibration and mode interpretation", ""])
    if report.mode is EvalMode.DETERMINISTIC_REGRESSION:
        lines.append("- Provider-free deterministic contract regression; this mode may gate CI.")
    elif report.mode is EvalMode.LIVE_CALIBRATION:
        lines.append("- Fresh provider-backed observational calibration; it is never a deterministic CI gate.")
    else:
        lines.append("- Recomputed from an immutable provider capture; it is not a fresh provider run.")
    lines.append("- Provider variance != code regression.")
    lines.append("- Contract correctness != reference-score agreement.")
    lines.extend(["", "## Known exclusions and limitations", ""])
    lines.extend(f"- {item}" for item in report.known_exclusions)
    if not report.known_exclusions:
        lines.append("- None recorded for this run.")
    return "\n".join(lines) + "\n"


def _report_case(mode: EvalMode, result) -> ReportCase:
    attribution = result.attribution
    calibration_mode = mode in {EvalMode.LIVE_CALIBRATION, EvalMode.CALIBRATION_REPLAY}
    severity = attribution.severity if attribution is not None else (
        EvalSeverity.MAJOR
        if result.status in {EvalStatus.BLOCKED, EvalStatus.INVALID_CASE}
        else EvalSeverity.INFO
    )
    return ReportCase(
        case_id=result.case_id,
        result_schema_version=(
            CALIBRATION_RESULT_SCHEMA_VERSION if calibration_mode else EVAL_RESULT_SCHEMA_VERSION
        ),
        status=result.status,
        severity=severity,
        findings=result.findings,
        first_failing_boundary=(attribution.first_boundary if attribution else None),
        failure_codes=(attribution.first_failure_codes if attribution else ()),
        calibration=result.calibration,
        provider_metadata=result.provider_metadata,
        provider_capture_id=result.provider_capture_id,
        blocked_or_invalid_reason=result.reason,
    )


__all__ = [
    "ReportCase",
    "ReportSummary",
    "StructuredEvalReport",
    "build_structured_report",
    "render_human_report",
]
