"""Provider-free deterministic final-outcome evaluation for P10-05."""

from collections.abc import Mapping

from pydantic import ValidationError

from app.eval.schemas import (
    EvalCategory,
    EvalFinding,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
    RegressionCase,
)


_CATEGORY_BOUNDARY: dict[EvalCategory, FailureBoundary] = {
    EvalCategory.PROVIDER_CONTRACT: FailureBoundary.PROVIDER_CONTRACT,
    EvalCategory.EVALUATION: FailureBoundary.EVALUATION,
    EvalCategory.PERSISTENCE: FailureBoundary.PERSISTENCE,
    EvalCategory.STATE: FailureBoundary.STATE,
    EvalCategory.MEMORY: FailureBoundary.MEMORY,
    EvalCategory.PLANNER: FailureBoundary.PLANNER,
    EvalCategory.RECOMMENDATION: FailureBoundary.RECOMMENDATION,
    EvalCategory.KNOWLEDGE: FailureBoundary.KNOWLEDGE,
    EvalCategory.PRACTICE: FailureBoundary.PRACTICE_GENERATION,
    EvalCategory.AGENT_TRAJECTORY: FailureBoundary.AGENT_TRAJECTORY,
    EvalCategory.AUTHORITY: FailureBoundary.AUTHORITY,
    EvalCategory.LIFECYCLE: FailureBoundary.LEARNING_UPDATE,
}

_SEVERITY_ORDER = (EvalSeverity.VETO, EvalSeverity.MAJOR, EvalSeverity.MINOR, EvalSeverity.INFO)


def evaluate_outcome(
    case: RegressionCase,
    observed: Mapping[str, object],
) -> EvalFinding:
    """Compare final application-owned observations with frozen case expectations."""

    if EvaluatorId.OUTCOME not in case.applicable_evaluators:
        return EvalFinding(
            evaluator=EvaluatorId.OUTCOME,
            status=EvalStatus.NOT_APPLICABLE,
            severity=EvalSeverity.INFO,
        )

    mismatch = _first_mismatch(case.expected_structured_outcomes, observed)
    if mismatch is None:
        return EvalFinding(
            evaluator=EvaluatorId.OUTCOME,
            status=EvalStatus.PASS,
            severity=EvalSeverity.INFO,
        )

    return EvalFinding(
        evaluator=EvaluatorId.OUTCOME,
        status=EvalStatus.FAIL,
        severity=_failure_severity(case),
        first_failing_boundary=_CATEGORY_BOUNDARY[case.category],
        failure_codes=(f"outcome_mismatch:{mismatch}",),
    )


def evaluate_outcome_record(
    case_record: Mapping[str, object],
    observed: Mapping[str, object],
) -> EvalFinding:
    """Fail closed when an untrusted case record cannot become a strict case."""

    try:
        case = RegressionCase.model_validate(case_record)
    except ValidationError:
        return EvalFinding(
            evaluator=EvaluatorId.OUTCOME,
            status=EvalStatus.INVALID_CASE,
            severity=EvalSeverity.VETO,
            failure_codes=("invalid_regression_case",),
        )
    return evaluate_outcome(case, observed)


def _first_mismatch(expected: Mapping[str, object], observed: Mapping[str, object], prefix: str = "") -> str | None:
    for key in sorted(expected):
        expected_value = expected[key]
        if key not in observed:
            return f"{prefix}{key}:missing"
        observed_value = observed[key]
        if isinstance(expected_value, Mapping):
            if not isinstance(observed_value, Mapping):
                return f"{prefix}{key}:type"
            nested = _first_mismatch(expected_value, observed_value, f"{prefix}{key}.")
            if nested is not None:
                return nested
        elif observed_value != expected_value:
            return f"{prefix}{key}:value"
    return None


def _failure_severity(case: RegressionCase) -> EvalSeverity:
    expected = {item.severity for item in case.severity_expectations}
    return next(severity for severity in _SEVERITY_ORDER if severity in expected)


__all__ = ["evaluate_outcome", "evaluate_outcome_record"]
