"""Minimal repository-native runner for the three frozen Phase 10 modes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Literal

from pydantic import Field

from app.eval.attribution import FailureAttribution, FindingEvidence, attribute_findings
from app.eval.calibration import (
    CalibrationAnalysis,
    CalibrationSample,
    analyze_calibration,
    sample_from_provider_capture,
)
from app.eval.corpora import CalibrationCorpus, RegressionCorpus
from app.eval.schemas import (
    CALIBRATION_CORPUS_VERSION,
    POLICY_VERSION,
    REGRESSION_CORPUS_VERSION,
    CalibrationCase,
    EvalFinding,
    EvalMode,
    EvalSchema,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
    ProviderCapture,
    RegressionCase,
)


RegressionExecutor = Callable[[RegressionCase], tuple[FindingEvidence, ...]]


class ProviderExecutionMetadata(EvalSchema):
    provider: str
    model: str
    prompt_version: str
    rubric_version: str
    scoring_policy_version: str
    run_config_version: str


class LiveCalibrationExecution(EvalSchema):
    sample: CalibrationSample
    provider_metadata: ProviderExecutionMetadata


LiveCalibrationExecutor = Callable[[CalibrationCase], LiveCalibrationExecution]


class RunnerCaseResult(EvalSchema):
    case_id: str
    mode: EvalMode
    status: EvalStatus
    findings: tuple[EvalFinding, ...] = ()
    attribution: FailureAttribution | None = None
    calibration: CalibrationAnalysis | None = None
    provider_metadata: ProviderExecutionMetadata | None = None
    provider_capture_id: str | None = None
    reason: str | None = None


class RunnerSuiteResult(EvalSchema):
    run_id: str
    policy_version: Literal["writing-eval-calibration-v1"] = POLICY_VERSION
    mode: EvalMode
    corpus_version: Literal[
        "writing-eval-regression-corpus-v1",
        "writing-score-calibration-corpus-v1",
    ]
    cases: tuple[RunnerCaseResult, ...] = ()
    status: EvalStatus
    blocked_reason: str | None = None


class EvalRunner:
    """Execute bounded, ordered cases without owning production behavior."""

    def __init__(self, *, max_cases: int = 100) -> None:
        if max_cases <= 0:
            raise ValueError("max_cases must be positive")
        self._max_cases = max_cases

    def run_deterministic(
        self,
        *,
        run_id: str,
        corpus: RegressionCorpus,
        executors: Mapping[str, RegressionExecutor],
        selected_case_ids: frozenset[str] | None = None,
    ) -> RunnerSuiteResult:
        cases = self._selected(corpus.cases, selected_case_ids)
        if not cases:
            return RunnerSuiteResult(
                run_id=run_id,
                mode=EvalMode.DETERMINISTIC_REGRESSION,
                corpus_version=REGRESSION_CORPUS_VERSION,
                status=EvalStatus.INVALID_CASE,
                blocked_reason="no_cases_selected",
            )
        results: list[RunnerCaseResult] = []
        for case in cases:
            executor = executors.get(case.case_id)
            if executor is None:
                results.append(self._invalid_case(case, "unregistered_case_executor"))
                continue
            try:
                evidence = executor(case)
                executed = {item.finding.evaluator for item in evidence}
                if not set(case.applicable_evaluators).issubset(executed):
                    results.append(self._invalid_case(case, "applicable_evaluator_not_executed"))
                    continue
                attribution = attribute_findings(
                    mode=EvalMode.DETERMINISTIC_REGRESSION,
                    evidence=evidence,
                )
                results.append(
                    RunnerCaseResult(
                        case_id=case.case_id,
                        mode=EvalMode.DETERMINISTIC_REGRESSION,
                        status=attribution.status,
                        findings=tuple(item.finding for item in evidence),
                        attribution=attribution,
                    )
                )
            except Exception:
                results.append(self._blocked_case(case, "case_executor_failed"))
        return RunnerSuiteResult(
            run_id=run_id,
            mode=EvalMode.DETERMINISTIC_REGRESSION,
            corpus_version=REGRESSION_CORPUS_VERSION,
            cases=tuple(results),
            status=_suite_status(results),
        )

    def run_live_calibration(
        self,
        *,
        run_id: str,
        corpus: CalibrationCorpus,
        provider: LiveCalibrationExecutor | None,
    ) -> RunnerSuiteResult:
        if not corpus.cases:
            return _blocked_suite(
                run_id,
                EvalMode.LIVE_CALIBRATION,
                "insufficient_reference_data",
            )
        if provider is None:
            return _blocked_suite(
                run_id,
                EvalMode.LIVE_CALIBRATION,
                "live_provider_not_injected",
            )
        results: list[RunnerCaseResult] = []
        for case in self._selected(corpus.cases, None):
            try:
                execution = provider(case)
                if execution.sample.case.case_id != case.case_id:
                    raise ValueError("provider result case identity mismatch")
                if execution.sample.mode is not EvalMode.LIVE_CALIBRATION:
                    raise ValueError("live provider must return live_calibration evidence")
                calibration = analyze_calibration((execution.sample,))
                results.append(
                    RunnerCaseResult(
                        case_id=case.case_id,
                        mode=EvalMode.LIVE_CALIBRATION,
                        status=calibration.status,
                        calibration=calibration,
                        provider_metadata=execution.provider_metadata,
                    )
                )
            except Exception:
                results.append(
                    RunnerCaseResult(
                        case_id=case.case_id,
                        mode=EvalMode.LIVE_CALIBRATION,
                        status=EvalStatus.BLOCKED,
                    )
                )
        return RunnerSuiteResult(
            run_id=run_id,
            mode=EvalMode.LIVE_CALIBRATION,
            corpus_version=CALIBRATION_CORPUS_VERSION,
            cases=tuple(results),
            status=_suite_status(results),
        )

    def run_calibration_replay(
        self,
        *,
        run_id: str,
        corpus: CalibrationCorpus,
        captures: tuple[ProviderCapture, ...],
    ) -> RunnerSuiteResult:
        if not corpus.cases:
            return _blocked_suite(
                run_id,
                EvalMode.CALIBRATION_REPLAY,
                "insufficient_reference_data",
            )
        capture_by_case = {capture.case_id: capture for capture in captures}
        results: list[RunnerCaseResult] = []
        for case in self._selected(corpus.cases, None):
            capture = capture_by_case.get(case.case_id)
            if capture is None:
                results.append(
                    RunnerCaseResult(
                        case_id=case.case_id,
                        mode=EvalMode.CALIBRATION_REPLAY,
                        status=EvalStatus.BLOCKED,
                    )
                )
                continue
            try:
                sample = sample_from_provider_capture(case, capture)
                calibration = analyze_calibration((sample,))
                results.append(
                    RunnerCaseResult(
                        case_id=case.case_id,
                        mode=EvalMode.CALIBRATION_REPLAY,
                        status=calibration.status,
                        calibration=calibration,
                        provider_metadata=ProviderExecutionMetadata(
                            provider=capture.provider,
                            model=capture.model,
                            prompt_version=capture.prompt_version,
                            rubric_version=capture.rubric_version,
                            scoring_policy_version=capture.scoring_policy_version,
                            run_config_version=capture.run_config_version,
                        ),
                        provider_capture_id=capture.capture_id,
                    )
                )
            except Exception:
                results.append(
                    RunnerCaseResult(
                        case_id=case.case_id,
                        mode=EvalMode.CALIBRATION_REPLAY,
                        status=EvalStatus.INVALID_CASE,
                        provider_capture_id=capture.capture_id,
                    )
                )
        return RunnerSuiteResult(
            run_id=run_id,
            mode=EvalMode.CALIBRATION_REPLAY,
            corpus_version=CALIBRATION_CORPUS_VERSION,
            cases=tuple(results),
            status=_suite_status(results),
        )

    def _selected(self, cases, selected_case_ids: frozenset[str] | None):
        selected = tuple(
            sorted(
                (
                    case
                    for case in cases
                    if selected_case_ids is None or case.case_id in selected_case_ids
                ),
                key=lambda case: case.case_id,
            )
        )
        if len(selected) > self._max_cases:
            raise ValueError("selected case count exceeds runner bound")
        return selected

    @staticmethod
    def _invalid_case(case: RegressionCase, code: str) -> RunnerCaseResult:
        finding = EvalFinding(
            evaluator=EvaluatorId.OUTCOME,
            status=EvalStatus.INVALID_CASE,
            severity=EvalSeverity.VETO,
            failure_codes=(code,),
        )
        attribution = attribute_findings(
            mode=EvalMode.DETERMINISTIC_REGRESSION,
            evidence=(FindingEvidence(finding=finding, boundary=FailureBoundary.CASE_VALIDATION),),
        )
        return RunnerCaseResult(
            case_id=case.case_id,
            mode=EvalMode.DETERMINISTIC_REGRESSION,
            status=attribution.status,
            findings=(finding,),
            attribution=attribution,
        )

    @staticmethod
    def _blocked_case(case: RegressionCase, code: str) -> RunnerCaseResult:
        finding = EvalFinding(
            evaluator=EvaluatorId.OUTCOME,
            status=EvalStatus.BLOCKED,
            severity=EvalSeverity.VETO,
            failure_codes=(code,),
        )
        attribution = attribute_findings(
            mode=EvalMode.DETERMINISTIC_REGRESSION,
            evidence=(FindingEvidence(finding=finding, boundary=FailureBoundary.INFRASTRUCTURE),),
        )
        return RunnerCaseResult(
            case_id=case.case_id,
            mode=EvalMode.DETERMINISTIC_REGRESSION,
            status=attribution.status,
            findings=(finding,),
            attribution=attribution,
        )


def _suite_status(results: list[RunnerCaseResult]) -> EvalStatus:
    for status in (
        EvalStatus.INVALID_CASE,
        EvalStatus.BLOCKED,
        EvalStatus.FAIL,
    ):
        if any(result.status is status for result in results):
            return status
    return EvalStatus.PASS


def _blocked_suite(run_id: str, mode: EvalMode, reason: str) -> RunnerSuiteResult:
    return RunnerSuiteResult(
        run_id=run_id,
        mode=mode,
        corpus_version=CALIBRATION_CORPUS_VERSION,
        status=EvalStatus.BLOCKED,
        blocked_reason=reason,
    )


__all__ = [
    "EvalRunner",
    "LiveCalibrationExecution",
    "ProviderExecutionMetadata",
    "RunnerCaseResult",
    "RunnerSuiteResult",
]
