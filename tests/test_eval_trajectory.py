"""P10-06 trajectory evaluator tests over public AgentTurnResponse evidence."""

from app.eval.trajectory import evaluate_trajectory
from app.schemas.agent import (
    AgentObservation,
    AgentOutcome,
    AgentStep,
    AgentStopReason,
    AgentTool,
    AgentTurnResponse,
    ObservationKind,
)


def _response(*steps: AgentStep, stop: AgentStopReason = AgentStopReason.NEEDS_INITIAL_WRITING) -> AgentTurnResponse:
    observation = AgentObservation(kind=ObservationKind.NEEDS_INITIAL_WRITING)
    return AgentTurnResponse(
        initial_observation=observation,
        steps=list(steps),
        final_observation=observation,
        stop_reason=stop,
    )


def _observe() -> AgentStep:
    return AgentStep(tool=AgentTool.OBSERVE, outcome=AgentOutcome.OBSERVATION_CLASSIFIED)


def test_valid_public_trajectory_is_repeatable() -> None:
    response = _response(_observe())

    assert evaluate_trajectory(response) == evaluate_trajectory(response)
    assert evaluate_trajectory(response).status.value == "pass"


def test_missing_required_initial_observation_fails() -> None:
    response = _response(
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.PRACTICE_GENERATED),
        stop=AgentStopReason.PRACTICE_READY,
    )

    assert evaluate_trajectory(response).failure_codes == ("trajectory_missing_initial_observation",)


def test_generation_bound_violation_fails_without_inspecting_free_text() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.PRACTICE_GENERATED),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.PRACTICE_GENERATED),
        stop=AgentStopReason.PRACTICE_READY,
    )

    finding = evaluate_trajectory(response)
    assert finding.severity.value == "veto"
    assert finding.failure_codes == ("trajectory_generation_bound",)


def test_submission_conflict_must_stop_safely() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_CONFLICT),
        stop=AgentStopReason.NEEDS_PRACTICE_SUBMISSION,
    )

    assert evaluate_trajectory(response).failure_codes == ("trajectory_conflict_not_terminal",)


def test_stale_generation_requires_bounded_stop() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.GENERATION_STALE_DISCARDED),
        stop=AgentStopReason.PRACTICE_READY,
    )

    assert evaluate_trajectory(response).failure_codes == ("trajectory_stale_generation_not_bounded",)
