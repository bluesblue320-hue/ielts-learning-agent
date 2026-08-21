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
    PracticeSubmissionAgentTurn,
)

MAX_MUTATING_TOOL_EXECUTIONS = 3
MAX_OBSERVATIONS = 4


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
        active_turn = turn

        while mutations < MAX_MUTATING_TOOL_EXECUTIONS:
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
                        steps.append(
                            AgentStep(
                                tool=AgentTool.SUBMIT_PRACTICE,
                                outcome=AgentOutcome.SUBMISSION_CONFLICT,
                            )
                        )
                        return self._response(
                            initial,
                            steps,
                            observed,
                            AgentStopReason.SUBMISSION_CONFLICT,
                        )
                    result = await self._tools.submit_practice(
                        learner_id=learner_id,
                        practice_id=active_turn.practice_id,
                        essay=active_turn.essay,
                    )
                    outcome = {
                        "submitted": AgentOutcome.SUBMISSION_SUBMITTED,
                        "reused": AgentOutcome.SUBMISSION_REUSED,
                        "in_progress": AgentOutcome.SUBMISSION_IN_PROGRESS,
                        "conflict": AgentOutcome.SUBMISSION_CONFLICT,
                    }[result.status]
                    steps.append(AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=outcome))
                    mutations += 1
                    if result.status == "in_progress":
                        return self._response(
                            initial, steps, observed, AgentStopReason.AWAIT_SUBMISSION
                        )
                    if result.status == "conflict":
                        return self._response(
                            initial,
                            steps,
                            observed,
                            AgentStopReason.SUBMISSION_CONFLICT,
                        )
                    if not replay.completion_applied:
                        completed = self._tools.complete_practice(
                            learner_id=learner_id,
                            practice_id=active_turn.practice_id,
                        )
                        steps.append(
                            AgentStep(
                                tool=AgentTool.COMPLETE_PRACTICE,
                                outcome=(
                                    AgentOutcome.COMPLETION_REUSED
                                    if completed.reused
                                    else AgentOutcome.COMPLETION_APPLIED
                                ),
                            )
                        )
                        mutations += 1
                    if observations >= MAX_OBSERVATIONS:
                        return self._response(
                            initial, steps, observed, AgentStopReason.MAX_ACTIONS
                        )
                    observed = self._observe(learner_id)
                    steps.append(
                        AgentStep(
                            tool=AgentTool.OBSERVE,
                            outcome=AgentOutcome.OBSERVATION_CLASSIFIED,
                        )
                    )
                    observations += 1
                    active_turn = ContinueAgentTurn(turn_type="continue")
                    continue

            selected = select_agent_action(observed=observed, turn=active_turn)
            if selected.action == AgentAction.STOP:
                assert selected.stop_reason is not None
                return self._response(initial, steps, observed, selected.stop_reason)
            if selected.action == AgentAction.SUBMISSION_CONFLICT:
                steps.append(
                    AgentStep(
                        tool=AgentTool.SUBMIT_PRACTICE,
                        outcome=AgentOutcome.SUBMISSION_CONFLICT,
                    )
                )
                return self._response(
                    initial, steps, observed, AgentStopReason.SUBMISSION_CONFLICT
                )
            if selected.action == AgentAction.GENERATE_PRACTICE:
                assert observed.recommendation_id is not None
                assert observed.latest_learning_update_id is not None
                generated = await self._tools.generate_practice(
                    learner_id=learner_id,
                    recommendation_id=observed.recommendation_id,
                    expected_learning_update_id=observed.latest_learning_update_id,
                )
                steps.append(
                    AgentStep(
                        tool=AgentTool.GENERATE_PRACTICE,
                        outcome={
                            "generated": AgentOutcome.PRACTICE_GENERATED,
                            "resolved": AgentOutcome.PRACTICE_RESOLVED,
                            "stale_discarded": AgentOutcome.GENERATION_STALE_DISCARDED,
                        }[generated.status],
                    )
                )
                mutations += 1
            elif selected.action == AgentAction.SUBMIT_PRACTICE:
                assert observed.practice_id is not None
                result = await self._tools.submit_practice(
                    learner_id=learner_id,
                    practice_id=observed.practice_id,
                    essay=active_turn.essay,
                )
                outcome = {
                    "submitted": AgentOutcome.SUBMISSION_SUBMITTED,
                    "reused": AgentOutcome.SUBMISSION_REUSED,
                    "in_progress": AgentOutcome.SUBMISSION_IN_PROGRESS,
                    "conflict": AgentOutcome.SUBMISSION_CONFLICT,
                }[result.status]
                steps.append(AgentStep(tool=AgentTool.SUBMIT_PRACTICE, outcome=outcome))
                mutations += 1
                if result.status in {"submitted", "reused"}:
                    active_turn = ContinueAgentTurn(turn_type="continue")
                if result.status == "in_progress":
                    return self._response(
                        initial, steps, observed, AgentStopReason.AWAIT_SUBMISSION
                    )
                if result.status == "conflict":
                    return self._response(
                        initial, steps, observed, AgentStopReason.SUBMISSION_CONFLICT
                    )
            elif selected.action == AgentAction.COMPLETE_PRACTICE:
                assert observed.practice_id is not None
                completed = self._tools.complete_practice(
                    learner_id=learner_id, practice_id=observed.practice_id
                )
                steps.append(
                    AgentStep(
                        tool=AgentTool.COMPLETE_PRACTICE,
                        outcome=(
                            AgentOutcome.COMPLETION_REUSED
                            if completed.reused
                            else AgentOutcome.COMPLETION_APPLIED
                        ),
                    )
                )
                mutations += 1
            else:  # pragma: no cover - closed selector enum
                raise AssertionError(f"unsupported agent action: {selected.action}")

            if observations >= MAX_OBSERVATIONS:
                return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)
            observed = self._observe(learner_id)
            steps.append(
                AgentStep(tool=AgentTool.OBSERVE, outcome=AgentOutcome.OBSERVATION_CLASSIFIED)
            )
            observations += 1

        return self._response(initial, steps, observed, AgentStopReason.MAX_ACTIONS)

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