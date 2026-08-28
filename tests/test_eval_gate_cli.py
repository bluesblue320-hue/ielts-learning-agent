"""P10-15 deterministic gate entrypoint safety tests."""

import sys
from types import SimpleNamespace

from app.eval import gate


def test_gate_requires_isolated_postgresql_url(monkeypatch) -> None:
    monkeypatch.delenv("IELTS_TEST_DATABASE_URL", raising=False)

    assert gate.main() == 2


def test_gate_removes_provider_key_and_runs_only_frozen_targets(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv(
        "IELTS_TEST_DATABASE_URL",
        "postgresql+psycopg://test-user@localhost:5432/ielts_test",
    )
    monkeypatch.setenv("IELTS_DEEPSEEK_API_KEY", "must-not-reach-gate")
    monkeypatch.setitem(
        sys.modules,
        "pytest",
        SimpleNamespace(main=lambda args: calls.append(args) or 0),
    )

    assert gate.main() == 0
    assert "IELTS_DEEPSEEK_API_KEY" not in __import__("os").environ
    assert calls == [["-q", "--strict-markers", *gate.DETERMINISTIC_GATE_TARGETS]]
    joined = " ".join(gate.DETERMINISTIC_GATE_TARGETS)
    assert "lifecycle_integration" in joined
    assert "live_calibration" not in joined
    assert "test_eval_calibration.py" not in joined
