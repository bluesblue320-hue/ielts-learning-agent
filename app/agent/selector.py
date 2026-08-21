"""Pure deterministic selection over one authoritative Agent observation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.agent.observation import AgentObservedState
from app.schemas.agent import (
    AgentStopReason,
    ContinueAgentTurn,
    ObservationKind,
    PracticeSubmissionAgentTurn,
)
from app.services.practice_submission import submission_fingerprint


class AgentAction(StrEnum):
    STOP = "stop"
    GENERATE_PRACTICE = "generate_practice"
    SUBMIT_PRACTICE = "submit_practice"
    COMPLETE_PRACTICE = "complete_practice"
    SUBMISSION_CONFLICT = "submission_conflict"


class AgentStalePracticeError(Exception):
    """An explicit essay targets a practice that is no longer current."""


class AgentSelectionError(Exception):
    """The explicit turn is incompatible with the authoritative state."""


@dataclass(frozen=True)
class AgentSelection:
    action: AgentAction
    stop_reason: AgentStopReason | None = None


def select_agent_action(
    *,
    observed: AgentObservedState,
    turn: ContinueAgentTurn | PracticeSubmissionAgentTurn,
) -> AgentSelection:
    """Choose exactly one deterministic next step without side effects."""

    kind = observed.observation.kind
    if isinstance(turn, ContinueAgentTurn):
        return _select_continue(kind, observed)
    return _select_submission(turn, observed)


def _select_continue(kind: ObservationKind, observed: AgentObservedState) -> AgentSelection:
    if kind == ObservationKind.NEEDS_INITIAL_WRITING:
        return AgentSelection(AgentAction.STOP, AgentStopReason.NEEDS_INITIAL_WRITING)
    if kind == ObservationKind.NO_PRACTICE:
        reasons = observed.observation.no_practice_reason_codes
        assert reasons is not None  # validated by AgentObservation
        return AgentSelection(
            AgentAction.STOP,
            AgentStopReason.TARGET_ACHIEVED
            if reasons[0].value == "target_achieved"
            else AgentStopReason.NO_PRACTICE,
        )
    if kind == ObservationKind.NEEDS_GENERATION:
        return AgentSelection(AgentAction.GENERATE_PRACTICE)
    if kind == ObservationKind.NEEDS_PRACTICE_SUBMISSION:
        return AgentSelection(
            AgentAction.STOP, AgentStopReason.NEEDS_PRACTICE_SUBMISSION
        )
    if kind == ObservationKind.AWAIT_SUBMISSION:
        return AgentSelection(AgentAction.STOP, AgentStopReason.AWAIT_SUBMISSION)
    if kind == ObservationKind.NEEDS_COMPLETION:
        return AgentSelection(AgentAction.COMPLETE_PRACTICE)
    raise AgentSelectionError(f"unsupported observation kind: {kind}")


def _select_submission(
    turn: PracticeSubmissionAgentTurn,
    observed: AgentObservedState,
) -> AgentSelection:
    if observed.practice is None or observed.practice_id != turn.practice_id:
        raise AgentStalePracticeError("practice submission is not for the current practice")
    if observed.observation.kind not in {
        ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        ObservationKind.AWAIT_SUBMISSION,
        ObservationKind.NEEDS_COMPLETION,
    }:
        raise AgentSelectionError("practice submission is not valid for this state")
    fingerprint = submission_fingerprint(
        practice_id=observed.practice_id,
        question=observed.practice.question,
        essay=turn.essay,
    )
    if (
        observed.practice_submission_fingerprint is not None
        and observed.practice_submission_fingerprint != fingerprint
    ):
        return AgentSelection(
            AgentAction.SUBMISSION_CONFLICT, AgentStopReason.SUBMISSION_CONFLICT
        )
    return AgentSelection(AgentAction.SUBMIT_PRACTICE)
