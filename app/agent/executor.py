"""Bounded deterministic executor for one explicit Core Learning Agent turn."""

from __future__ import annotations

from collections.abc import Callable

from app.agent.observation import AgentObservedState
from app.agent.selector import AgentAction, select_agent_action
from app.agent.tools import AgentTools
from app.schemas.agent import (
    AgentObservation,
    AgentOutcome,
    AgentStep,
    AgentStopReason,
    AgentTool,
    AgentTurn,
    AgentTurnResponse,
    ContinueAgentTurn,
    ObservationKind,
    PracticeSubmissionAgentTurn,
)

MAX_MUTATING_TOOL_EXECUTIONS = 3
MAX_OBSERVATIONS = 4
MAX_PROVIDER_BACKED_SERVICE_INVOCATIONS = 2
MAX_AUTOMATIC_GENERATIONS = 1
MAX_AUTOMATIC_COMPLETIONS = 1


class AgentTurnExecutor:
    """Coordinates deterministic service calls with frozen per-turn bounds."""

    def __init__(
        self,
        *,
        tools: AgentTools,
        observe: Callable[[int], AgentObservedState],
    ) -> None:
        self._tools = tools
        self._observe = observe

    async def execute(self, *, learner_id: int, turn: AgentTurn) -> AgentTurnResponse:
        observed = self._observe(learner_id)
        initial = observed.observation
        steps = [AgentStep(tool=AgentTool.OBSERVE, outcome=AgentOutcome.OBSERVATION_CLASSIFIED)]
        observations = 1
        mutations = 0
        provider_invocations = 0
        automatic_generations = 0
        automatic_completions = 0
        prepared_practice_this_turn = False
        active_turn = turn

        while True:
            if mutations >= MAX_MUTATING_TOOL_EXECUTIONS:
                return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)

            if (
                isinstance(active_turn, PracticeSubmissionAgentTurn)
                and observed.practice_id != active_turn.practice_id
            ):
                replay = self._tools.resolve_submitted_replay(
                    learner_id=learner_id,
                    practice_id=active_turn.practice_id,
                    essay=active_turn.essay,
                )
                if replay is not None:
                    if not replay.matches:
                        steps.append(AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_CONFLICT))
                        return self._response(initial, steps, observed, AgentStopReason.SUBMISSION_CONFLICT)
                    result = await self._tools.submit_practice(
                        learner_id=learner_id,
                        practice_id=active_turn.practice_id,
                        essay=active_turn.essay,
                    )
                    steps.append(AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=self._submission_outcome(result.status)))
                    mutations += 1
                    if result.status == "in_progress":
                        return self._response(initial, steps, observed, AgentStopReason.AWAIT_SUBMISSION)
                    if result.status == "conflict":
                        return self._response(initial, steps, observed, AgentStopReason.SUBMISSION_CONFLICT)
                    if not replay.completion_applied:
                        if automatic_completions >= MAX_AUTOMATIC_COMPLETIONS or mutations >= MAX_MUTATING_TOOL_EXECUTIONS:
                            return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)
                        completed = self._tools.complete_practice(learner_id=learner_id, practice_id=active_turn.practice_id)
                        steps.append(AgentStep(tool=AgentTool.COMPLETE_PRACTICE, outcome=(AgentOutcome.COMPLETION_REUSED if completed.reused else AgentOutcome.COMPLETION_APPLIED)))
                        mutations += 1
                        automatic_completions += 1
                    observed, observations, exhausted = self._reobserve(learner_id, steps, observations, observed)
                    if exhausted:
                        return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)
                    active_turn = ContinueAgentTurn(turn_type="continue")
                    continue

            selected = select_agent_action(observed=observed, turn=active_turn)
            if selected.action == AgentAction.STOP:
                assert selected.stop_reason is not None
                stop_reason = selected.stop_reason
                if (
                    prepared_practice_this_turn
                    and stop_reason == AgentStopReason.NEEDS_PRACTICE_SUBMISSION
                ):
                    stop_reason = AgentStopReason.PRACTICE_READY
                return self._response(initial, steps, observed, stop_reason)
            if selected.action == AgentAction.SUBMISSION_CONFLICT:
                steps.append(AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=AgentOutcome.SUBMISSION_CONFLICT))
                return self._response(initial, steps, observed, AgentStopReason.SUBMISSION_CONFLICT)
            if selected.action == AgentAction.GENERATE_PRACTICE:
                if (
                    automatic_generations >= MAX_AUTOMATIC_GENERATIONS
                    or provider_invocations >= MAX_PROVIDER_BACKED_SERVICE_INVOCATIONS
                ):
                    return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)
                assert observed.recommendation_id is not None
                assert observed.latest_learning_update_id is not None
                generated = await self._tools.generate_practice(
                    learner_id=learner_id,
                    recommendation_id=observed.recommendation_id,
                    expected_learning_update_id=observed.latest_learning_update_id,
                )
                automatic_generations += 1
                mutations += 1
                provider_invocations += int(getattr(generated, "provider_invoked", generated.status == "generated"))
                steps.append(AgentStep(tool=AgentTool.GENERATE_PRACTICE, outcome={
                    "generated": AgentOutcome.PRACTICE_GENERATED,
                    "resolved": AgentOutcome.PRACTICE_RESOLVED,
                    "stale_discarded": AgentOutcome.GENERATION_STALE_DISCARDED,
                }[generated.status]))
                prepared_practice_this_turn = generated.status in {"generated", "resolved"}
            elif selected.action == AgentAction.SUBMIT_PRACTICE:
                if provider_invocations >= MAX_PROVIDER_BACKED_SERVICE_INVOCATIONS:
                    return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)
                assert observed.practice_id is not None
                result = await self._tools.submit_practice(
                    learner_id=learner_id,
                    practice_id=observed.practice_id,
                    essay=active_turn.essay,
                    expected_learning_update_id=observed.latest_learning_update_id,
                    expected_recommendation_id=observed.recommendation_id,
                )
                mutations += 1
                provider_invocations += int(result.status == "submitted")
                steps.append(AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=self._submission_outcome(result.status)))
                if result.status in {"submitted", "reused"}:
                    active_turn = ContinueAgentTurn(turn_type="continue")
                if result.status == "in_progress":
                    return self._response(initial, steps, observed, AgentStopReason.AWAIT_SUBMISSION)
                if result.status == "conflict":
                    return self._response(initial, steps, observed, AgentStopReason.SUBMISSION_CONFLICT)
            elif selected.action == AgentAction.COMPLETE_PRACTICE:
                if automatic_completions >= MAX_AUTOMATIC_COMPLETIONS:
                    return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)
                assert observed.practice_id is not None
                completed = self._tools.complete_practice(learner_id=learner_id, practice_id=observed.practice_id)
                steps.append(AgentStep(tool=AgentTool.COMPLETE_PRACTICE, outcome=(AgentOutcome.COMPLETION_REUSED if completed.reused else AgentOutcome.COMPLETION_APPLIED)))
                mutations += 1
                automatic_completions += 1
            else:  # pragma: no cover - closed selector enum
                raise AssertionError(f"unsupported agent action: {selected.action}")

            observed, observations, exhausted = self._reobserve(learner_id, steps, observations, observed)
            if exhausted:
                return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)

    def _reobserve(
        self,
        learner_id: int,
        steps: list[AgentStep],
        observations: int,
        observed: AgentObservedState,
    ) -> tuple[AgentObservedState, int, bool]:
        if observations >= MAX_OBSERVATIONS:
            return observed, observations, True
        fresh = self._observe(learner_id)
        steps.append(
            AgentStep(tool=AgentTool.OBSERVE, outcome=AgentOutcome.OBSERVATION_CLASSIFIED)
        )
        return fresh, observations + 1, False
    @staticmethod
    def _submission_outcome(status: str) -> AgentOutcome:
        return {
            "submitted": AgentOutcome.SUBMISSION_SUBMITTED,
            "reused": AgentOutcome.SUBMISSION_REUSED,
            "in_progress": AgentOutcome.SUBMISSION_IN_PROGRESS,
            "conflict": AgentOutcome.SUBMISSION_CONFLICT,
        }[status]

    @staticmethod
    def _response(
        initial: AgentObservation,
        steps: list[AgentStep],
        observed: AgentObservedState,
        stop_reason: AgentStopReason,
    ) -> AgentTurnResponse:
        return AgentTurnResponse(
            initial_observation=initial,
            steps=steps,
            final_observation=observed.observation,
            stop_reason=stop_reason,
            current_recommendation=observed.recommendation,
            current_practice=observed.practice,
        )