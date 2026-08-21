"""Strict public contracts for one bounded Phase 8 Writing Agent Turn."""

from enum import StrEnum
from typing import Annotated, Final, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.planning import PublicPracticeRecommendationDecision
from app.schemas.practice import PracticeResponse
from app.schemas.writing import WritingEssayText


class AgentVersion(StrEnum):
    WRITING_CORE_LEARNING_AGENT_V1 = "writing-core-learning-agent-v1"


class ObservationVersion(StrEnum):
    WRITING_AGENT_OBSERVATION_V1 = "writing-agent-observation-v1"


AGENT_OBSERVATION_VERSION: Final[ObservationVersion] = (
    ObservationVersion.WRITING_AGENT_OBSERVATION_V1
)


class ObservationKind(StrEnum):
    NEEDS_INITIAL_WRITING = "needs_initial_writing"
    NO_PRACTICE = "no_practice"
    NEEDS_GENERATION = "needs_generation"
    NEEDS_PRACTICE_SUBMISSION = "needs_practice_submission"
    AWAIT_SUBMISSION = "await_submission"
    NEEDS_COMPLETION = "needs_completion"


class NoPracticeReason(StrEnum):
    TARGET_ACHIEVED = "target_achieved"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    COLD_START = "cold_start"
    INCOMPLETE_STATE = "incomplete_state"
    TARGET_UNSET = "target_unset"


_VALID_NO_PRACTICE_REASON_SEQUENCES = {
    (NoPracticeReason.TARGET_ACHIEVED,),
    (
        NoPracticeReason.TARGET_ACHIEVED,
        NoPracticeReason.INSUFFICIENT_EVIDENCE,
    ),
    (NoPracticeReason.COLD_START,),
    (NoPracticeReason.INCOMPLETE_STATE,),
    (NoPracticeReason.TARGET_UNSET,),
}


class ContinueAgentTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_type: Literal["continue"]


class PracticeSubmissionAgentTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_type: Literal["practice_submission"]
    practice_id: int = Field(gt=0)
    essay: WritingEssayText


AgentTurnRequest = Annotated[
    Union[ContinueAgentTurn, PracticeSubmissionAgentTurn],
    Field(discriminator="turn_type"),
]
AgentTurn = AgentTurnRequest


class AgentTool(StrEnum):
    OBSERVE = "observe"
    GENERATE_PRACTICE = "generate_practice"
    SUBMIT_PRACTICE = "submit_practice"
    COMPLETE_PRACTICE = "complete_practice"


class AgentOutcome(StrEnum):
    OBSERVATION_CLASSIFIED = "observation_classified"
    PRACTICE_GENERATED = "practice_generated"
    PRACTICE_RESOLVED = "practice_resolved"
    GENERATION_STALE_DISCARDED = "generation_stale_discarded"
    SUBMISSION_SUBMITTED = "submission_submitted"
    SUBMISSION_REUSED = "submission_reused"
    SUBMISSION_IN_PROGRESS = "submission_in_progress"
    SUBMISSION_CONFLICT = "submission_conflict"
    COMPLETION_APPLIED = "completion_applied"
    COMPLETION_REUSED = "completion_reused"


_TOOL_OUTCOMES = {
    AgentTool.OBSERVE: {AgentOutcome.OBSERVATION_CLASSIFIED},
    AgentTool.GENERATE_PRACTICE: {
        AgentOutcome.PRACTICE_GENERATED,
        AgentOutcome.PRACTICE_RESOLVED,
        AgentOutcome.GENERATION_STALE_DISCARDED,
    },
    AgentTool.SUBMIT_PRACTICE: {
        AgentOutcome.SUBMISSION_SUBMITTED,
        AgentOutcome.SUBMISSION_REUSED,
        AgentOutcome.SUBMISSION_IN_PROGRESS,
        AgentOutcome.SUBMISSION_CONFLICT,
    },
    AgentTool.COMPLETE_PRACTICE: {
        AgentOutcome.COMPLETION_APPLIED,
        AgentOutcome.COMPLETION_REUSED,
    },
}


class AgentObservation(BaseModel):
    """Public-safe classification; internal ids and claim metadata stay private."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ObservationKind
    no_practice_reason_codes: list[NoPracticeReason] | None = None

    @model_validator(mode="after")
    def _validate_reason_sequence(self) -> "AgentObservation":
        if self.kind == ObservationKind.NO_PRACTICE:
            if self.no_practice_reason_codes is None:
                raise ValueError("no_practice observation requires reason codes")
            sequence = tuple(self.no_practice_reason_codes)
            if sequence not in _VALID_NO_PRACTICE_REASON_SEQUENCES:
                raise ValueError("invalid no_practice reason sequence")
        elif self.no_practice_reason_codes is not None:
            raise ValueError(
                "only no_practice observations may carry no_practice reason codes"
            )
        return self


class AgentStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool: AgentTool
    outcome: AgentOutcome

    @model_validator(mode="after")
    def _validate_tool_outcome(self) -> "AgentStep":
        if self.outcome not in _TOOL_OUTCOMES[self.tool]:
            raise ValueError("outcome is not valid for tool")
        return self


class AgentStopReason(StrEnum):
    NEEDS_INITIAL_WRITING = "needs_initial_writing"
    NEEDS_PRACTICE_SUBMISSION = "needs_practice_submission"
    PRACTICE_READY = "practice_ready"
    AWAIT_SUBMISSION = "await_submission"
    TARGET_ACHIEVED = "target_achieved"
    NO_PRACTICE = "no_practice"
    SUBMISSION_CONFLICT = "submission_conflict"
    MAX_ACTIONS = "max_actions"


class AgentTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_version: AgentVersion = AgentVersion.WRITING_CORE_LEARNING_AGENT_V1
    initial_observation: AgentObservation
    steps: list[AgentStep] = Field(default_factory=list, max_length=7)
    final_observation: AgentObservation
    stop_reason: AgentStopReason
    current_recommendation: PublicPracticeRecommendationDecision | None = None
    current_practice: PracticeResponse | None = None


__all__ = [
    "AGENT_OBSERVATION_VERSION",
    "AgentObservation",
    "AgentOutcome",
    "AgentStep",
    "AgentStopReason",
    "AgentTool",
    "AgentTurn",
    "AgentTurnRequest",
    "AgentTurnResponse",
    "AgentVersion",
    "ContinueAgentTurn",
    "NoPracticeReason",
    "ObservationKind",
    "ObservationVersion",
    "PracticeSubmissionAgentTurn",
]
