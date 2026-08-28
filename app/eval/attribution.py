"""Frozen Phase 10 failure ordering and first-boundary attribution."""

from __future__ import annotations

from pydantic import model_validator

from app.eval.schemas import (
    EvalFinding,
    EvalMode,
    EvalSchema,
    EvalSeverity,
    EvalStatus,
    FailureBoundary,
)


BOUNDARY_ORDER = tuple(FailureBoundary)
_BOUNDARY_INDEX = {boundary: index for index, boundary in enumerate(BOUNDARY_ORDER)}
_SEVERITY_ORDER = (
    EvalSeverity.VETO,
    EvalSeverity.MAJOR,
    EvalSeverity.MINOR,
    EvalSeverity.INFO,
)
_STATUS_ORDER = (
    EvalStatus.INVALID_CASE,
    EvalStatus.BLOCKED,
    EvalStatus.FAIL,
    EvalStatus.PASS,
    EvalStatus.NOT_APPLICABLE,
)


class FindingEvidence(EvalSchema):
    """An executed finding with an explicit boundary for non-fail outcomes."""

    finding: EvalFinding
    boundary: FailureBoundary | None = None

    @model_validator(mode="after")
    def boundary_matches_execution_status(self) -> "FindingEvidence":
        if self.finding.status in {
            EvalStatus.FAIL,
            EvalStatus.BLOCKED,
            EvalStatus.INVALID_CASE,
        } and self.effective_boundary is None:
            raise ValueError("Failed, blocked, or invalid evidence requires a boundary.")
        if self.finding.status in {EvalStatus.PASS, EvalStatus.NOT_APPLICABLE} and self.boundary is not None:
            raise ValueError("Successful or inapplicable evidence cannot add a failure boundary.")
        return self

    @property
    def effective_boundary(self) -> FailureBoundary | None:
        return self.finding.first_failing_boundary or self.boundary


class FailureAttribution(EvalSchema):
    status: EvalStatus
    severity: EvalSeverity
    first_boundary: FailureBoundary | None = None
    first_failure_codes: tuple[str, ...] = ()
    deterministic_gate_failed: bool
    contract_regression: bool


def attribute_findings(
    *,
    mode: EvalMode,
    evidence: tuple[FindingEvidence, ...],
) -> FailureAttribution:
    """Reduce executed findings without inventing downstream failures."""

    if not evidence:
        raise ValueError("Attribution requires at least one executed finding.")
    status = next(
        candidate
        for candidate in _STATUS_ORDER
        if any(item.finding.status is candidate for item in evidence)
    )
    severity = next(
        candidate
        for candidate in _SEVERITY_ORDER
        if any(item.finding.severity is candidate for item in evidence)
    )
    causal = tuple(
        item
        for item in evidence
        if item.finding.status is status
        and item.effective_boundary is not None
    )
    first = min(
        causal,
        key=lambda item: _BOUNDARY_INDEX[item.effective_boundary],
        default=None,
    )
    boundary = first.effective_boundary if first is not None else None
    codes = first.finding.failure_codes if first is not None else ()
    deterministic_gate_failed = (
        mode is EvalMode.DETERMINISTIC_REGRESSION
        and (
            status in {EvalStatus.INVALID_CASE, EvalStatus.BLOCKED}
            or (status is EvalStatus.FAIL and severity in {EvalSeverity.VETO, EvalSeverity.MAJOR})
        )
    )
    contract_regression = (
        mode is EvalMode.DETERMINISTIC_REGRESSION
        and status is EvalStatus.FAIL
        and boundary is not FailureBoundary.CALIBRATION
    )
    return FailureAttribution(
        status=status,
        severity=severity,
        first_boundary=boundary,
        first_failure_codes=codes,
        deterministic_gate_failed=deterministic_gate_failed,
        contract_regression=contract_regression,
    )


__all__ = [
    "BOUNDARY_ORDER",
    "FailureAttribution",
    "FindingEvidence",
    "attribute_findings",
]
