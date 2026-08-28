"""Portable local/CI entrypoint for the provider-free Phase 10 Eval gate."""

from __future__ import annotations

import os
import sys


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
)


def main() -> int:
    """Run only deterministic, provider-free gate targets against isolated PG."""

    if not os.getenv("IELTS_TEST_DATABASE_URL"):
        print("IELTS_TEST_DATABASE_URL is required for the deterministic Eval gate.", file=sys.stderr)
        return 2
    os.environ.pop("IELTS_DEEPSEEK_API_KEY", None)
    import pytest

    return pytest.main(["-q", "--strict-markers", *DETERMINISTIC_GATE_TARGETS])


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DETERMINISTIC_GATE_TARGETS", "main"]
