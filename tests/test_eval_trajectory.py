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


def _response(
    *steps: AgentStep,
    initial: ObservationKind = ObservationKind.NEEDS_INITIAL_WRITING,
    final: ObservationKind | None = None,
    stop: AgentStopReason = AgentStopReason.NEEDS_INITIAL_WRITING,
) -> AgentTurnResponse:
    initial_observation = AgentObservation(kind=initial)
    return AgentTurnResponse(
        initial_observation=initial_observation,
        steps=list(steps),
        final_observation=AgentObservation(kind=final or initial),
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
        initial=ObservationKind.NEEDS_GENERATION,
        stop=AgentStopReason.PRACTICE_READY,
    )

    assert evaluate_trajectory(response).failure_codes == ("trajectory_missing_initial_observation",)


def test_generation_requires_valid_observed_state() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.PRACTICE_GENERATED),
        stop=AgentStopReason.PRACTICE_READY,
    )

    assert evaluate_trajectory(response).failure_codes == ("trajectory_generation_without_valid_state",)


def test_generation_bound_violation_fails_without_inspecting_free_text() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.PRACTICE_GENERATED),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.PRACTICE_GENERATED),
        initial=ObservationKind.NEEDS_GENERATION,
        stop=AgentStopReason.PRACTICE_READY,
    )

    finding = evaluate_trajectory(response)
    assert finding.severity.value == "veto"
    assert finding.failure_codes == ("trajectory_generation_bound",)


def test_submission_requires_existing_practice_context() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_SUBMITTED),
        initial=ObservationKind.NEEDS_GENERATION,
    )

    assert evaluate_trajectory(response).failure_codes == ("trajectory_submission_without_practice_context",)


def test_completion_requires_submission_context_and_rejects_reordered_flow() -> None:
    missing_submission = _response(
        _observe(),
        AgentStep(tool=AgentTool.COMPLETE_PRACTICE, outcome=AgentOutcome.COMPLETION_APPLIED),
    )
    reordered = _response(
        _observe(),
        AgentStep(tool=AgentTool.COMPLETE_PRACTICE, outcome=AgentOutcome.COMPLETION_APPLIED),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_SUBMITTED),
        initial=ObservationKind.NEEDS_COMPLETION,
    )

    assert evaluate_trajectory(missing_submission).failure_codes == ("trajectory_completion_without_submission_context",)
    assert evaluate_trajectory(reordered).failure_codes == ("trajectory_submission_after_completion",)


def test_submission_conflict_and_in_progress_are_terminal_for_mutations() -> None:
    conflict = _response(
        _observe(),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_CONFLICT),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.PRACTICE_GENERATED),
        initial=ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        stop=AgentStopReason.SUBMISSION_CONFLICT,
    )
    in_progress = _response(
        _observe(),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_IN_PROGRESS),
        AgentStep(tool=AgentTool.COMPLETE_PRACTICE, outcome=AgentOutcome.COMPLETION_APPLIED),
        initial=ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        stop=AgentStopReason.AWAIT_SUBMISSION,
    )

    assert evaluate_trajectory(conflict).failure_codes == ("trajectory_mutation_after_terminal_submission_conflict",)
    assert evaluate_trajectory(in_progress).failure_codes == ("trajectory_mutation_after_terminal_submission_in_progress",)


def test_submission_conflict_must_stop_safely() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_CONFLICT),
        initial=ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        stop=AgentStopReason.NEEDS_PRACTICE_SUBMISSION,
    )

    assert evaluate_trajectory(response).failure_codes == ("trajectory_conflict_not_terminal",)


def test_valid_replay_and_reuse_trajectory_remains_allowed() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_REUSED),
        _observe(),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.PRACTICE_RESOLVED),
        _observe(),
        initial=ObservationKind.NEEDS_GENERATION,
        final=ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        stop=AgentStopReason.PRACTICE_READY,
    )

    assert evaluate_trajectory(response).status.value == "pass"


def test_single_submission_reuse_remains_allowed() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_REUSED),
        initial=ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        final=ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        stop=AgentStopReason.PRACTICE_READY,
    )

    assert evaluate_trajectory(response).status.value == "pass"


def test_duplicate_mutating_submission_is_rejected() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_SUBMITTED),
        AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_REUSED),
        initial=ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        stop=AgentStopReason.NEEDS_PRACTICE_SUBMISSION,
    )

    finding = evaluate_trajectory(response)

    assert finding.severity.value == "veto"
    assert finding.failure_codes == ("trajectory_duplicate_submission",)


def test_stale_generation_requires_bounded_stop() -> None:
    response = _response(
        _observe(),
        AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome=AgentOutcome.GENERATION_STALE_DISCARDED),
        initial=ObservationKind.NEEDS_GENERATION,
        stop=AgentStopReason.PRACTICE_READY,
    )

    assert evaluate_trajectory(response).failure_codes == ("trajectory_stale_generation_not_bounded",)