"""P10-05 deterministic Outcome evaluator coverage."""

from app.eval.outcome import evaluate_outcome, evaluate_outcome_record
from app.eval.schemas import (
    EvalCategory,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
    ProvenanceReference,
    RegressionCase,
    SeverityExpectation,
)


def _case(*, evaluators: tuple[EvaluatorId, ...] = (EvaluatorId.OUTCOME,), severity: EvalSeverity = EvalSeverity.MAJOR) -> RegressionCase:
    return RegressionCase(
        case_id="outcome-example",
        description="Outcome contract example.",
        category=EvalCategory.EVALUATION,
        input={"fixture": "example"},
        expected_structured_outcomes={"status": "accepted", "nested": {"count": 1}},
        applicable_evaluators=evaluators,
        severity_expectations=(
            SeverityExpectation(boundary=FailureBoundary.EVALUATION, severity=severity),
        ),
        provenance=ProvenanceReference(source="test", locator="outcome"),
    )


def test_outcome_evaluator_passes_repeated_matching_observation() -> None:
    case = _case()
    observed = {"status": "accepted", "nested": {"count": 1}}

    first = evaluate_outcome(case, observed)
    second = evaluate_outcome(case, observed)

    assert first == second
    assert first.status == EvalStatus.PASS


def test_outcome_evaluator_reports_first_deterministic_mismatch() -> None:
    finding = evaluate_outcome(_case(), {"status": "accepted", "nested": {"count": 2}})

    assert finding.status == EvalStatus.FAIL
    assert finding.severity == EvalSeverity.MAJOR
    assert finding.first_failing_boundary == FailureBoundary.EVALUATION
    assert finding.failure_codes == ("outcome_mismatch:nested.count:value",)


def test_outcome_evaluator_keeps_veto_severity_visible() -> None:
    finding = evaluate_outcome(_case(severity=EvalSeverity.VETO), {"status": "rejected", "nested": {"count": 1}})

    assert finding.status == EvalStatus.FAIL
    assert finding.severity == EvalSeverity.VETO


def test_outcome_evaluator_returns_not_applicable_without_comparing() -> None:
    finding = evaluate_outcome(_case(evaluators=(EvaluatorId.AUTHORITY,)), {})

    assert finding.status == EvalStatus.NOT_APPLICABLE


def test_outcome_evaluator_marks_invalid_untrusted_case_without_pass() -> None:
    finding = evaluate_outcome_record({"case_id": "invalid"}, {"status": "accepted"})

    assert finding.status == EvalStatus.INVALID_CASE
    assert finding.severity == EvalSeverity.VETO
