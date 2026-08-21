"""P8-08 bounded executor tests."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.agent.executor import AgentTurnExecutor
from app.agent.observation import AgentObservedState
from app.schemas.practice import PracticeLifecycleState, PracticeResponse

from app.schemas.agent import (
    AgentObservation,
    AgentOutcome,
    AgentStopReason,
    ContinueAgentTurn,
    NoPracticeReason,
    ObservationKind,
    PracticeSubmissionAgentTurn,
)


def _state(kind: ObservationKind) -> AgentObservedState:
    practice = (
        PracticeResponse(
            id=9, learner_id=1, recommendation_id=5, target_skill="task_response",
            question="Question", focus_objective="Objective", instructions=["Do it"],
            checkpoints=["Check it"], practice_type="writing_task_2",
            generator_policy_version="writing-practice-generation-v1", provider="fake",
            model="fake", prompt_version="v1", thinking_mode="disabled",
            lifecycle_state=PracticeLifecycleState.GENERATED, attempt_id=None,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        if kind in {ObservationKind.NEEDS_PRACTICE_SUBMISSION, ObservationKind.NEEDS_COMPLETION}
        else None
    )
    reasons = (
        [NoPracticeReason.TARGET_ACHIEVED]
        if kind == ObservationKind.NO_PRACTICE
        else None
    )
    return AgentObservedState(
        observation=AgentObservation(kind=kind, no_practice_reason_codes=reasons),
        latest_learning_update_id=4,
        recommendation_id=5,
        practice_id=9 if practice else None,
        recommendation=None,
        practice=practice,
        practice_lifecycle_state=None,
        practice_submission_fingerprint=None,
        practice_evaluation_id=None,
        practice_completion_applied=False,
    )


class Tools:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.replay = None
        self.submission_status = "submitted"

    async def generate_practice(self, **_kwargs):
        self.calls.append("generate")
        return SimpleNamespace(status="generated")

    async def submit_practice(self, **_kwargs):
        self.calls.append("submit")
        return SimpleNamespace(status=self.submission_status)

    def resolve_submitted_replay(self, **_kwargs):
        self.calls.append("resolve")
        return self.replay

    def complete_practice(self, **_kwargs):
        self.calls.append("complete")
        return SimpleNamespace(reused=False)


def _executor(states: list[AgentObservedState], tools: Tools) -> AgentTurnExecutor:
    iterator = iter(states)
    return AgentTurnExecutor(tools=tools, observe=lambda _learner_id: next(iterator))


def test_continue_generates_once_then_reports_new_practice_ready() -> None:
    tools = Tools()
    response = asyncio.run(
        _executor(
            [_state(ObservationKind.NEEDS_GENERATION), _state(ObservationKind.NEEDS_PRACTICE_SUBMISSION)],
            tools,
        ).execute(learner_id=1, turn=ContinueAgentTurn(turn_type="continue"))
    )
    assert tools.calls == ["generate"]
    assert [step.outcome for step in response.steps] == [
        AgentOutcome.OBSERVATION_CLASSIFIED,
        AgentOutcome.PRACTICE_GENERATED,
        AgentOutcome.OBSERVATION_CLASSIFIED,
    ]
    assert response.stop_reason == AgentStopReason.PRACTICE_READY


def test_submission_reobserves_completes_and_stops_truthfully() -> None:
    tools = Tools()
    response = asyncio.run(
        _executor(
            [
                _state(ObservationKind.NEEDS_PRACTICE_SUBMISSION),
                _state(ObservationKind.NEEDS_COMPLETION),
                _state(ObservationKind.NO_PRACTICE),
            ],
            tools,
        ).execute(
            learner_id=1,
            turn=PracticeSubmissionAgentTurn(
                turn_type="practice_submission", practice_id=9, essay="Essay."
            ),
        )
    )
    assert tools.calls == ["submit", "complete"]
    assert response.stop_reason == AgentStopReason.TARGET_ACHIEVED
    assert len(response.steps) == 5


def test_live_submission_claim_stops_without_a_second_action() -> None:
    tools = Tools()
    tools.submit_practice = lambda **_kwargs: _async_result("in_progress")
    response = asyncio.run(
        _executor([_state(ObservationKind.NEEDS_PRACTICE_SUBMISSION)], tools).execute(
            learner_id=1,
            turn=PracticeSubmissionAgentTurn(
                turn_type="practice_submission", practice_id=9, essay="Essay."
            ),
        )
    )
    assert response.stop_reason == AgentStopReason.AWAIT_SUBMISSION
    assert response.steps[-1].outcome == AgentOutcome.SUBMISSION_IN_PROGRESS


async def _async_result(status: str):
    return SimpleNamespace(status=status)


def test_historical_submitted_replay_skips_applied_completion_and_continues() -> None:
    tools = Tools()
    tools.replay = SimpleNamespace(matches=True, completion_applied=True)
    tools.submission_status = "reused"
    response = asyncio.run(
        _executor(
            [
                _state(ObservationKind.NEEDS_GENERATION),
                _state(ObservationKind.NEEDS_GENERATION),
                _state(ObservationKind.NEEDS_PRACTICE_SUBMISSION),
            ],
            tools,
        ).execute(
            learner_id=1,
            turn=PracticeSubmissionAgentTurn(
                turn_type="practice_submission", practice_id=7, essay="Essay."
            ),
        )
    )
    assert tools.calls == ["resolve", "submit", "generate"]
    assert [step.outcome for step in response.steps] == [
        AgentOutcome.OBSERVATION_CLASSIFIED,
        AgentOutcome.SUBMISSION_REUSED,
        AgentOutcome.OBSERVATION_CLASSIFIED,
        AgentOutcome.PRACTICE_GENERATED,
        AgentOutcome.OBSERVATION_CLASSIFIED,
    ]
    assert response.stop_reason == AgentStopReason.PRACTICE_READY

def test_stale_generation_consumes_the_single_automatic_generation_budget() -> None:
    tools = Tools()
    tools.generate_practice = lambda **_kwargs: _record_generation(tools, "stale_discarded", False)
    response = asyncio.run(
        _executor(
            [_state(ObservationKind.NEEDS_GENERATION), _state(ObservationKind.NEEDS_GENERATION)], tools
        ).execute(learner_id=1, turn=ContinueAgentTurn(turn_type="continue"))
    )
    assert response.stop_reason == AgentStopReason.MAX_ACTIONS
    assert tools.calls == ["generate"]
    assert len([step for step in response.steps if step.tool.value == "observe"]) == 2


def test_completion_budget_stops_before_a_second_automatic_completion() -> None:
    tools = Tools()
    response = asyncio.run(
        _executor(
            [_state(ObservationKind.NEEDS_COMPLETION), _state(ObservationKind.NEEDS_COMPLETION)], tools
        ).execute(learner_id=1, turn=ContinueAgentTurn(turn_type="continue"))
    )
    assert response.stop_reason == AgentStopReason.MAX_ACTIONS
    assert tools.calls == ["complete"]


def test_turn_never_exceeds_frozen_mutation_provider_or_observation_bounds() -> None:
    tools = Tools()
    response = asyncio.run(
        _executor(
            [
                _state(ObservationKind.NEEDS_PRACTICE_SUBMISSION),
                _state(ObservationKind.NEEDS_COMPLETION),
                _state(ObservationKind.NEEDS_GENERATION),
                _state(ObservationKind.NEEDS_PRACTICE_SUBMISSION),
            ], tools
        ).execute(
            learner_id=1,
            turn=PracticeSubmissionAgentTurn(
                turn_type="practice_submission", practice_id=9, essay="Essay."
            ),
        )
    )
    assert response.stop_reason == AgentStopReason.MAX_ACTIONS
    assert tools.calls == ["submit", "complete", "generate"]
    assert len(tools.calls) <= 3
    assert len([step for step in response.steps if step.tool.value == "observe"]) <= 4


async def _generation(status: str, provider_invoked: bool):
    return SimpleNamespace(status=status, provider_invoked=provider_invoked)
async def _record_generation(tools: Tools, status: str, provider_invoked: bool):
    tools.calls.append("generate")
    return await _generation(status, provider_invoked)


def test_provider_budget_independently_blocks_third_provider_call(monkeypatch) -> None:
    """Provider limit is a gate even when other per-turn limits are relaxed."""
    import app.agent.executor as executor_module

    monkeypatch.setattr(executor_module, "MAX_MUTATING_TOOL_EXECUTIONS", 10)
    monkeypatch.setattr(executor_module, "MAX_AUTOMATIC_GENERATIONS", 10)
    monkeypatch.setattr(executor_module, "MAX_OBSERVATIONS", 10)
    tools = Tools()
    tools.generate_practice = lambda **_kwargs: _record_generation(tools, "stale_discarded", True)
    response = asyncio.run(
        _executor(
            [
                _state(ObservationKind.NEEDS_GENERATION),
                _state(ObservationKind.NEEDS_GENERATION),
                _state(ObservationKind.NEEDS_GENERATION),
            ],
            tools,
        ).execute(learner_id=1, turn=ContinueAgentTurn(turn_type="continue"))
    )
    assert response.stop_reason == AgentStopReason.MAX_ACTIONS
    assert tools.calls == ["generate", "generate"]