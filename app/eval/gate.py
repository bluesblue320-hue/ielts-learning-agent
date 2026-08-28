"""Portable local/CI entrypoint for the provider-free Phase 10 Eval gate."""

from __future__ import annotations

import os
import sys

from app.eval.isolation import validate_test_database_url
from app.eval.regression_runtime import execute_canonical_regression
from app.eval.schemas import EvalStatus


DETERMINISTIC_GATE_TARGETS = (
    "tests/test_eval_schemas.py",
    "tests/test_eval_corpora.py",
    "tests/test_eval_outcome.py",
    "tests/test_eval_trajectory.py",
    "tests/test_eval_knowledge.py",
    "tests/test_eval_authority.py",
    "tests/test_eval_lifecycle.py",
    "tests/test_eval_lifecycle_integration.py",
    "tests/test_eval_attribution.py",
    "tests/test_eval_runner.py::test_deterministic_runner_orders_cases_and_executes_all_applicable_evaluators",
    "tests/test_eval_runner.py::test_unregistered_or_failed_case_does_not_corrupt_following_cases",
    "tests/test_eval_runner.py::test_runner_rejects_unbounded_case_selection",
    "tests/test_eval_runner.py::test_runner_rejects_empty_or_unknown_selection_without_fabricating_pass",
    "tests/test_eval_reporting.py::test_machine_report_preserves_versions_status_veto_and_first_failure",
    "tests/test_eval_reporting.py::test_human_report_is_stable_and_derived_from_structured_result",
    "tests/test_eval_regression_runtime.py::test_official_registry_exactly_covers_canonical_case_ids",
    "tests/test_eval_regression_runtime.py::test_registry_fails_closed_for_missing_unknown_and_duplicate_ids",
)


def suite_exit_code(status: EvalStatus) -> int:
    """Only a canonical PASS may produce a successful gate exit."""

    return 0 if status is EvalStatus.PASS else 1


def main() -> int:
    """Run framework tests, then the actual canonical provider-free suite."""

    database_url = os.getenv("IELTS_TEST_DATABASE_URL")
    if database_url is None:
        print(
            "IELTS_TEST_DATABASE_URL is required for the deterministic Eval gate.",
            file=sys.stderr,
        )
        return 2
    try:
        validate_test_database_url(database_url, os.getenv("IELTS_DATABASE_URL"))
    except ValueError as error:
        print(f"Eval database isolation rejected: {error}", file=sys.stderr)
        return 2

    os.environ.pop("IELTS_DEEPSEEK_API_KEY", None)
    import pytest

    self_test_code = pytest.main(
        ["-q", "--strict-markers", *DETERMINISTIC_GATE_TARGETS]
    )
    if self_test_code != 0:
        return int(self_test_code)
    try:
        execution = execute_canonical_regression(
            run_id="phase10-canonical-gate",
            database_url=database_url,
        )
    except Exception as error:
        print(
            f"Canonical regression infrastructure failure: {type(error).__name__}",
            file=sys.stderr,
        )
        return 2
    print(execution.human_report, end="")
    return suite_exit_code(execution.suite.status)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DETERMINISTIC_GATE_TARGETS", "main", "suite_exit_code"]
