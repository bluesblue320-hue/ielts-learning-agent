"""P8-07 deterministic selection tests."""

from types import SimpleNamespace

import pytest

from app.agent.observation import AgentObservedState
from app.agent.selector import (
    AgentAction,
    AgentStalePracticeError,
    select_agent_action,
)
from app.schemas.agent import (
    AgentObservation,
    AgentStopReason,
    ContinueAgentTurn,
    NoPracticeReason,
    ObservationKind,
    PracticeSubmissionAgentTurn,
)
from app.services.practice_submission import submission_fingerprint


def _state(kind: ObservationKind, *, fingerprint: str | None = None):
    practice = (
        SimpleNamespace(id=9, question="Persisted question")
        if kind
        in {
            ObservationKind.NEEDS_PRACTICE_SUBMISSION,
            ObservationKind.AWAIT_SUBMISSION,
            ObservationKind.NEEDS_COMPLETION,
        }
        else None
    )
    return AgentObservedState(
        observation=AgentObservation(kind=kind),
        latest_learning_update_id=4,
        recommendation_id=5,
        practice_id=9 if practice else None,
        recommendation=None,
        practice=practice,
        practice_lifecycle_state=None,
        practice_submission_fingerprint=fingerprint,
        practice_evaluation_id=None,
        practice_completion_applied=False,
    )


@pytest.mark.parametrize(
    ("kind", "action", "stop"),
    [
        (ObservationKind.NEEDS_INITIAL_WRITING, AgentAction.STOP, AgentStopReason.NEEDS_INITIAL_WRITING),
        (ObservationKind.NEEDS_GENERATION, AgentAction.GENERATE_PRACTICE, None),
        (ObservationKind.NEEDS_PRACTICE_SUBMISSION, AgentAction.STOP, AgentStopReason.NEEDS_PRACTICE_SUBMISSION),
        (ObservationKind.AWAIT_SUBMISSION, AgentAction.STOP, AgentStopReason.AWAIT_SUBMISSION),
        (ObservationKind.NEEDS_COMPLETION, AgentAction.COMPLETE_PRACTICE, None),
    ],
)
def test_continue_selection_table(kind, action, stop) -> None:
    selected = select_agent_action(observed=_state(kind), turn=ContinueAgentTurn(turn_type="continue"))
    assert selected.action == action
    assert selected.stop_reason == stop


def test_no_practice_primary_reason_controls_stop() -> None:
    state = AgentObservedState(
        observation=AgentObservation(
            kind=ObservationKind.NO_PRACTICE,
            no_practice_reason_codes=[
                NoPracticeReason.TARGET_ACHIEVED,
                NoPracticeReason.INSUFFICIENT_EVIDENCE,
            ],
        ),
        latest_learning_update_id=4,
        recommendation_id=5,
        practice_id=None,
        recommendation=None,
        practice=None,
        practice_lifecycle_state=None,
        practice_submission_fingerprint=None,
        practice_evaluation_id=None,
        practice_completion_applied=False,
    )
    selected = select_agent_action(
        observed=state, turn=ContinueAgentTurn(turn_type="continue")
    )
    assert selected.stop_reason == AgentStopReason.TARGET_ACHIEVED


def test_matching_live_claim_delegates_to_submission_service() -> None:
    essay = "Same essay."
    fingerprint = submission_fingerprint(practice_id=9, question="Persisted question", essay=essay)
    selected = select_agent_action(
        observed=_state(ObservationKind.AWAIT_SUBMISSION, fingerprint=fingerprint),
        turn=PracticeSubmissionAgentTurn(turn_type="practice_submission", practice_id=9, essay=essay),
    )
    assert selected.action == AgentAction.SUBMIT_PRACTICE


def test_different_fingerprint_is_conflict_without_service() -> None:
    selected = select_agent_action(
        observed=_state(ObservationKind.NEEDS_COMPLETION, fingerprint="different"),
        turn=PracticeSubmissionAgentTurn(turn_type="practice_submission", practice_id=9, essay="Essay."),
    )
    assert selected.action == AgentAction.SUBMISSION_CONFLICT
    assert selected.stop_reason == AgentStopReason.SUBMISSION_CONFLICT


def test_old_generated_practice_is_rejected_before_evaluation() -> None:
    with pytest.raises(AgentStalePracticeError):
        select_agent_action(
            observed=_state(ObservationKind.NEEDS_PRACTICE_SUBMISSION),
            turn=PracticeSubmissionAgentTurn(turn_type="practice_submission", practice_id=10, essay="Essay."),
        )
