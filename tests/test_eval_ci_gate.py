"""P10-15 workflow wiring contract tests."""

from pathlib import Path


def test_ci_runs_phase_10_deterministic_gate_before_full_backend_suite() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    gate_command = "run: python -m app.eval.gate"
    full_suite = "run: python -m pytest -q --strict-markers"
    assert "phase/10-writing-evaluation-calibration-v1" in workflow
    assert gate_command in workflow
    assert workflow.index(gate_command) < workflow.index(full_suite)
    assert "live_calibration" not in workflow
    assert "IELTS_DEEPSEEK_API_KEY" not in workflow
