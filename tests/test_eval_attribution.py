"""P10-11 failure taxonomy, first-cause, and gate semantics."""

from app.eval.attribution import FindingEvidence, attribute_findings
from app.eval.schemas import (
    EvalFinding,
    EvalMode,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)


def _finding(
    *,
    status: EvalStatus,
    severity: EvalSeverity,
    boundary: FailureBoundary | None = None,
    code: str = "test-failure",
    evaluator: EvaluatorId = EvaluatorId.OUTCOME,
) -> FindingEvidence:
    return FindingEvidence(
        finding=EvalFinding(
            evaluator=evaluator,
            status=status,
            severity=severity,
            first_failing_boundary=boundary if status is EvalStatus.FAIL else None,
            failure_codes=(code,) if status is not EvalStatus.PASS else (),
        ),
        boundary=boundary if status is not EvalStatus.FAIL else None,
    )


def test_single_failure_is_attributed_to_its_boundary() -> None:
    result = attribute_findings(
        mode=EvalMode.DETERMINISTIC_REGRESSION,
        evidence=(
            _finding(
                status=EvalStatus.FAIL,
                severity=EvalSeverity.MAJOR,
                boundary=FailureBoundary.EVALUATION,
                code="score_contract_mismatch",
            ),
        ),
    )

    assert result.first_boundary is FailureBoundary.EVALUATION
    assert result.first_failure_codes == ("score_contract_mismatch",)
    assert result.deterministic_gate_failed is True


def test_first_boundary_is_deterministic_while_veto_severity_wins() -> None:
    result = attribute_findings(
        mode=EvalMode.DETERMINISTIC_REGRESSION,
        evidence=(
            _finding(
                status=EvalStatus.FAIL,
                severity=EvalSeverity.VETO,
                boundary=FailureBoundary.AUTHORITY,
                code="authority_bypass",
                evaluator=EvaluatorId.AUTHORITY,
            ),
            _finding(
                status=EvalStatus.FAIL,
                severity=EvalSeverity.MAJOR,
                boundary=FailureBoundary.PROVIDER_CONTRACT,
                code="provider_payload_invalid",
            ),
        ),
    )

    assert result.first_boundary is FailureBoundary.PROVIDER_CONTRACT
    assert result.first_failure_codes == ("provider_payload_invalid",)
    assert result.severity is EvalSeverity.VETO
    assert result.deterministic_gate_failed is True


def test_invalid_case_and_blocked_infrastructure_are_not_fabricated_passes() -> None:
    invalid = attribute_findings(
        mode=EvalMode.DETERMINISTIC_REGRESSION,
        evidence=(
            _finding(
                status=EvalStatus.INVALID_CASE,
                severity=EvalSeverity.VETO,
                boundary=FailureBoundary.CASE_VALIDATION,
                code="case_invalid",
            ),
        ),
    )
    blocked = attribute_findings(
        mode=EvalMode.DETERMINISTIC_REGRESSION,
        evidence=(
            _finding(
                status=EvalStatus.BLOCKED,
                severity=EvalSeverity.VETO,
                boundary=FailureBoundary.INFRASTRUCTURE,
                code="isolated_database_unavailable",
            ),
        ),
    )

    assert invalid.status is EvalStatus.INVALID_CASE
    assert invalid.first_boundary is FailureBoundary.CASE_VALIDATION
    assert blocked.status is EvalStatus.BLOCKED
    assert blocked.first_boundary is FailureBoundary.INFRASTRUCTURE
    assert invalid.deterministic_gate_failed and blocked.deterministic_gate_failed


def test_provider_failure_does_not_invent_downstream_failures() -> None:
    result = attribute_findings(
        mode=EvalMode.DETERMINISTIC_REGRESSION,
        evidence=(
            _finding(
                status=EvalStatus.FAIL,
                severity=EvalSeverity.VETO,
                boundary=FailureBoundary.PROVIDER_CONTRACT,
                code="provider_validation_failed",
            ),
        ),
    )

    assert result.first_boundary is FailureBoundary.PROVIDER_CONTRACT
    assert result.first_failure_codes == ("provider_validation_failed",)


def test_knowledge_and_authority_failures_preserve_frozen_boundaries() -> None:
    for boundary, evaluator in (
        (FailureBoundary.KNOWLEDGE, EvaluatorId.KNOWLEDGE_GROUNDING),
        (FailureBoundary.AUTHORITY, EvaluatorId.AUTHORITY),
    ):
        result = attribute_findings(
            mode=EvalMode.DETERMINISTIC_REGRESSION,
            evidence=(
                _finding(
                    status=EvalStatus.FAIL,
                    severity=EvalSeverity.VETO,
                    boundary=boundary,
                    evaluator=evaluator,
                ),
            ),
        )
        assert result.first_boundary is boundary


def test_calibration_disagreement_is_not_a_deterministic_contract_regression() -> None:
    result = attribute_findings(
        mode=EvalMode.CALIBRATION_REPLAY,
        evidence=(
            _finding(
                status=EvalStatus.FAIL,
                severity=EvalSeverity.MAJOR,
                boundary=FailureBoundary.CALIBRATION,
                code="reference_score_disagreement",
            ),
        ),
    )

    assert result.status is EvalStatus.FAIL
    assert result.first_boundary is FailureBoundary.CALIBRATION
    assert result.deterministic_gate_failed is False
    assert result.contract_regression is False
