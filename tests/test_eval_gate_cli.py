"""P10-15 canonical gate entrypoint safety and exit-semantic tests."""

import sys
from types import SimpleNamespace

import pytest

from app.eval import gate
from app.eval.schemas import EvalStatus


def test_gate_requires_isolated_postgresql_url(monkeypatch) -> None:
    monkeypatch.delenv("IELTS_TEST_DATABASE_URL", raising=False)

    assert gate.main() == 2


def test_gate_rejects_non_test_or_shared_database(monkeypatch) -> None:
    monkeypatch.setenv(
        "IELTS_TEST_DATABASE_URL",
        "postgresql+psycopg://user@localhost:5432/ielts_dev",
    )
    assert gate.main() == 2

    monkeypatch.setenv(
        "IELTS_TEST_DATABASE_URL",
        "postgresql+psycopg://user@localhost:5432/ielts_test",
    )
    monkeypatch.setenv(
        "IELTS_DATABASE_URL",
        "postgresql+psycopg://user@localhost:5432/ielts_test",
    )
    assert gate.main() == 2


@pytest.mark.parametrize(
    ("status", "expected_code"),
    (
        (EvalStatus.PASS, 0),
        (EvalStatus.FAIL, 1),
        (EvalStatus.BLOCKED, 1),
        (EvalStatus.INVALID_CASE, 1),
    ),
)
def test_gate_runs_self_tests_then_canonical_suite_and_enforces_status(
    monkeypatch,
    status: EvalStatus,
    expected_code: int,
) -> None:
    pytest_calls: list[list[str]] = []
    runtime_calls: list[tuple[str, str]] = []
    database_url = "postgresql+psycopg://test-user@localhost:5432/ielts_test"
    monkeypatch.setenv("IELTS_TEST_DATABASE_URL", database_url)
    monkeypatch.delenv("IELTS_DATABASE_URL", raising=False)
    monkeypatch.setenv("IELTS_DEEPSEEK_API_KEY", "must-not-reach-runtime")
    monkeypatch.setitem(
        sys.modules,
        "pytest",
        SimpleNamespace(main=lambda args: pytest_calls.append(args) or 0),
    )

    def execute(*, run_id: str, database_url: str):
        assert "IELTS_DEEPSEEK_API_KEY" not in __import__("os").environ
        runtime_calls.append((run_id, database_url))
        return SimpleNamespace(
            suite=SimpleNamespace(status=status),
            human_report="# canonical report\n",
        )

    monkeypatch.setattr(gate, "execute_canonical_regression", execute)

    assert gate.main() == expected_code
    assert pytest_calls == [
        ["-q", "--strict-markers", *gate.DETERMINISTIC_GATE_TARGETS]
    ]
    assert runtime_calls == [("phase10-canonical-gate", database_url)]
    joined = " ".join(gate.DETERMINISTIC_GATE_TARGETS)
    assert "lifecycle_integration" in joined
    assert "live_calibration" not in joined
    assert "test_eval_calibration.py" not in joined


def test_gate_stops_before_runtime_when_self_tests_fail(monkeypatch) -> None:
    monkeypatch.setenv(
        "IELTS_TEST_DATABASE_URL",
        "postgresql+psycopg://test-user@localhost:5432/ielts_test",
    )
    monkeypatch.setitem(sys.modules, "pytest", SimpleNamespace(main=lambda _args: 5))
    monkeypatch.setattr(
        gate,
        "execute_canonical_regression",
        lambda **_kwargs: pytest.fail(
            "canonical runtime must not run after self-test failure"
        ),
    )

    assert gate.main() == 5


def test_gate_returns_infrastructure_failure_for_runtime_exception(monkeypatch) -> None:
    monkeypatch.setenv(
        "IELTS_TEST_DATABASE_URL",
        "postgresql+psycopg://test-user@localhost:5432/ielts_test",
    )
    monkeypatch.setitem(sys.modules, "pytest", SimpleNamespace(main=lambda _args: 0))

    def fail(**_kwargs):
        raise RuntimeError("private infrastructure detail")

    monkeypatch.setattr(gate, "execute_canonical_regression", fail)

    assert gate.main() == 2
