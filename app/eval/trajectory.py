"""Structured, provider-free evaluation of frozen Agent turn trajectories."""

from app.agent.executor import (
    MAX_AUTOMATIC_COMPLETIONS,
    MAX_AUTOMATIC_GENERATIONS,
    MAX_MUTATING_TOOL_EXECUTIONS,
    MAX_OBSERVATIONS,
    MAX_PROVIDER_BACKED_SERVICE_INVOCATIONS,
)
from app.schemas.agent import AgentOutcome, AgentStopReason, AgentTool, AgentTurnResponse

from app.eval.schemas import (
    EvalFinding,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)


def evaluate_trajectory(response: AgentTurnResponse) -> EvalFinding:
    """Verify observable step order and bounds without inspecting model reasoning."""

    steps = response.steps
    if not steps or steps[0].tool != AgentTool.OBSERVE:
        return _failure("trajectory_missing_initial_observation", EvalSeverity.MAJOR)
    if any(step.tool == AgentTool.OBSERVE and step.outcome != AgentOutcome.OBSERVATION_CLASSIFIED for step in steps):
        return _failure("trajectory_invalid_observation_outcome", EvalSeverity.VETO)

    observations = sum(step.tool == AgentTool.OBSERVE for step in steps)
    mutations = sum(step.tool != AgentTool.OBSERVE for step in steps)
    generations = sum(step.tool == AgentTool.GENERATE_PRACTICE for step in steps)
    completions = sum(step.tool == AgentTool.COMPLETE_PRACTICE for step in steps)
    provider_calls = sum(
        step.outcome in {AgentOutcome.PRACTICE_GENERATED, AgentOutcome.SUBMISSION_SUBMITTED}
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

    if any(step.outcome == AgentOutcome.SUBMISSION_CONFLICT for step in steps):
        if response.stop_reason != AgentStopReason.SUBMISSION_CONFLICT:
            return _failure("trajectory_conflict_not_terminal", EvalSeverity.MAJOR)
    if any(step.outcome == AgentOutcome.SUBMISSION_IN_PROGRESS for step in steps):
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
