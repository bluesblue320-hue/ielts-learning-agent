"""Structured, provider-free evaluation of frozen Agent turn trajectories."""

from app.agent.executor import (
    MAX_AUTOMATIC_COMPLETIONS,
    MAX_AUTOMATIC_GENERATIONS,
    MAX_MUTATING_TOOL_EXECUTIONS,
    MAX_OBSERVATIONS,
    MAX_PROVIDER_BACKED_SERVICE_INVOCATIONS,
)
from app.schemas.agent import (
    AgentOutcome,
    AgentStopReason,
    AgentTool,
    AgentTurnResponse,
    ObservationKind,
)

from app.eval.schemas import (
    EvalFinding,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)


_PRACTICE_CONTEXT_OBSERVATIONS = {
    ObservationKind.NEEDS_PRACTICE_SUBMISSION,
    ObservationKind.NEEDS_COMPLETION,
}


def evaluate_trajectory(response: AgentTurnResponse) -> EvalFinding:
    """Validate observable Agent transitions and frozen execution bounds.

    This checker intentionally uses only public ``AgentTurnResponse`` fields.
    It never reconstructs a private executor trace or changes Agent behavior.
    """

    steps = response.steps
    if not steps or steps[0].tool != AgentTool.OBSERVE:
        return _failure("trajectory_missing_initial_observation", EvalSeverity.MAJOR)
    if any(
        step.tool == AgentTool.OBSERVE
        and step.outcome != AgentOutcome.OBSERVATION_CLASSIFIED
        for step in steps
    ):
        return _failure("trajectory_invalid_observation_outcome", EvalSeverity.VETO)

    observations = sum(step.tool == AgentTool.OBSERVE for step in steps)
    mutations = sum(step.tool != AgentTool.OBSERVE for step in steps)
    generations = sum(step.tool == AgentTool.GENERATE_PRACTICE for step in steps)
    completions = sum(step.tool == AgentTool.COMPLETE_PRACTICE for step in steps)
    provider_calls = sum(
        step.outcome
        in {AgentOutcome.PRACTICE_GENERATED, AgentOutcome.SUBMISSION_SUBMITTED}
        for step in steps
    )
    if observations > MAX_OBSERVATIONS:
        return _failure("trajectory_observation_bound", EvalSeverity.VETO)
    if mutations > MAX_MUTATING_TOOL_EXECUTIONS:
        return _failure("trajectory_mutation_bound", EvalSeverity.VETO)
    if generations > MAX_AUTOMATIC_GENERATIONS:
        return _failure("trajectory_generation_bound", EvalSeverity.VETO)
    if completions > MAX_AUTOMATIC_COMPLETIONS:
        return _failure("trajectory_completion_bound", EvalSeverity.VETO)
    if provider_calls > MAX_PROVIDER_BACKED_SERVICE_INVOCATIONS:
        return _failure("trajectory_provider_bound", EvalSeverity.VETO)

    has_practice_context = response.initial_observation.kind in _PRACTICE_CONTEXT_OBSERVATIONS
    has_submission_context = response.initial_observation.kind == ObservationKind.NEEDS_COMPLETION
    generated_this_turn = False
    completion_seen = False
    terminal_outcome: AgentOutcome | None = None

    for step in steps[1:]:
        if step.tool == AgentTool.OBSERVE:
            continue
        if terminal_outcome is not None:
            return _failure(
                f"trajectory_mutation_after_terminal_{terminal_outcome.value}",
                EvalSeverity.VETO,
            )

        if step.tool == AgentTool.GENERATE_PRACTICE:
            if (
                response.initial_observation.kind != ObservationKind.NEEDS_GENERATION
                and not completion_seen
            ):
                return _failure("trajectory_generation_without_valid_state", EvalSeverity.MAJOR)
            if step.outcome in {
                AgentOutcome.PRACTICE_GENERATED,
                AgentOutcome.PRACTICE_RESOLVED,
            }:
                has_practice_context = True
                generated_this_turn = True
            continue

        if step.tool == AgentTool.SUBMIT_PRACTICE:
            if completion_seen:
                return _failure("trajectory_submission_after_completion", EvalSeverity.VETO)
            if generated_this_turn:
                return _failure("trajectory_submission_reordered_after_generation", EvalSeverity.VETO)
            if (
                step.outcome != AgentOutcome.SUBMISSION_REUSED
                and not has_practice_context
            ):
                return _failure("trajectory_submission_without_practice_context", EvalSeverity.VETO)
            if step.outcome in {
                AgentOutcome.SUBMISSION_SUBMITTED,
                AgentOutcome.SUBMISSION_REUSED,
            }:
                has_submission_context = True
            if step.outcome in {
                AgentOutcome.SUBMISSION_CONFLICT,
                AgentOutcome.SUBMISSION_IN_PROGRESS,
            }:
                terminal_outcome = step.outcome
            continue

        if step.tool == AgentTool.COMPLETE_PRACTICE:
            if not has_submission_context:
                return _failure("trajectory_completion_without_submission_context", EvalSeverity.VETO)
            completion_seen = True

    if terminal_outcome == AgentOutcome.SUBMISSION_CONFLICT:
        if response.stop_reason != AgentStopReason.SUBMISSION_CONFLICT:
            return _failure("trajectory_conflict_not_terminal", EvalSeverity.MAJOR)
    if terminal_outcome == AgentOutcome.SUBMISSION_IN_PROGRESS:
        if response.stop_reason != AgentStopReason.AWAIT_SUBMISSION:
            return _failure("trajectory_in_progress_not_terminal", EvalSeverity.MAJOR)
    if any(step.outcome == AgentOutcome.GENERATION_STALE_DISCARDED for step in steps):
        if response.stop_reason != AgentStopReason.MAX_ACTIONS:
            return _failure("trajectory_stale_generation_not_bounded", EvalSeverity.MAJOR)

    return EvalFinding(
        evaluator=EvaluatorId.TRAJECTORY,
        status=EvalStatus.PASS,
        severity=EvalSeverity.INFO,
    )


def _failure(code: str, severity: EvalSeverity) -> EvalFinding:
    return EvalFinding(
        evaluator=EvaluatorId.TRAJECTORY,
        status=EvalStatus.FAIL,
        severity=severity,
        first_failing_boundary=FailureBoundary.AGENT_TRAJECTORY,
        failure_codes=(code,),
    )


__all__ = ["evaluate_trajectory"]