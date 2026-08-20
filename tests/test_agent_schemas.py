import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.agent import (
    AGENT_OBSERVATION_VERSION,
    AgentObservation,
    AgentOutcome,
    AgentStep,
    AgentStopReason,
    AgentTurnRequest,
    AgentTurnResponse,
    AgentVersion,
    ContinueAgentTurn,
    NoPracticeReason,
    ObservationKind,
    ObservationVersion,
    PracticeSubmissionAgentTurn,
)


def test_agent_versions_and_enum_sets_are_frozen() -> None:
    assert list(AgentVersion) == ["writing-core-learning-agent-v1"]
    assert list(ObservationVersion) == ["writing-agent-observation-v1"]
    assert AGENT_OBSERVATION_VERSION == "writing-agent-observation-v1"
    assert {item.value for item in ObservationKind} == {
        "needs_initial_writing",
        "no_practice",
        "needs_generation",
        "needs_practice_submission",
        "await_submission",
        "needs_completion",
    }
    assert {item.value for item in AgentStopReason} == {
        "needs_initial_writing",
        "needs_practice_submission",
        "practice_ready",
        "await_submission",
        "target_achieved",
        "no_practice",
        "submission_conflict",
        "max_actions",
    }
    assert {item.value for item in AgentOutcome} == {
        "observation_classified",
        "practice_generated",
        "practice_resolved",
        "generation_stale_discarded",
        "submission_submitted",
        "submission_reused",
        "submission_in_progress",
        "submission_conflict",
        "completion_applied",
        "completion_reused",
    }


def test_turn_request_is_a_strict_discriminated_union() -> None:
    adapter = TypeAdapter(AgentTurnRequest)

    assert adapter.validate_python({"turn_type": "continue"}) == ContinueAgentTurn(
        turn_type="continue"
    )
    assert adapter.validate_python(
        {
            "turn_type": "practice_submission",
            "practice_id": 17,
            "essay": "A sufficiently clear practice essay response.",
        }
    ) == PracticeSubmissionAgentTurn(
        turn_type="practice_submission",
        practice_id=17,
        essay="A sufficiently clear practice essay response.",
    )

    invalid_requests = (
        {"turn_type": "continue", "target_skill": "lexical_resource"},
        {"turn_type": "practice_submission", "practice_id": 0, "essay": "Essay"},
        {
            "turn_type": "practice_submission",
            "practice_id": 1,
            "question": "Untrusted question",
            "essay": "Essay",
        },
        {"turn_type": "initial_writing", "essay": "Essay"},
    )
    for payload in invalid_requests:
        with pytest.raises(ValidationError):
            adapter.validate_python(payload)


@pytest.mark.parametrize(
    "sequence,expected_stop",
    [
        (["target_achieved"], AgentStopReason.TARGET_ACHIEVED),
        (
            ["target_achieved", "insufficient_evidence"],
            AgentStopReason.TARGET_ACHIEVED,
        ),
        (["cold_start"], AgentStopReason.NO_PRACTICE),
        (["incomplete_state"], AgentStopReason.NO_PRACTICE),
        (["target_unset"], AgentStopReason.NO_PRACTICE),
    ],
)
def test_no_practice_accepts_only_planner_sequences(
    sequence: list[str], expected_stop: AgentStopReason
) -> None:
    observation = AgentObservation(
        kind="no_practice",
        no_practice_reason_codes=sequence,
    )
    assert [item.value for item in observation.no_practice_reason_codes or []] == sequence
    assert (
        AgentStopReason.TARGET_ACHIEVED
        if observation.no_practice_reason_codes[0]
        == NoPracticeReason.TARGET_ACHIEVED
        else AgentStopReason.NO_PRACTICE
    ) == expected_stop


@pytest.mark.parametrize(
    "sequence",
    [
        None,
        [],
        ["insufficient_evidence"],
        ["target_achieved", "cold_start"],
        ["cold_start", "insufficient_evidence"],
    ],
)
def test_no_practice_rejects_invented_sequences(
    sequence: list[str] | None,
) -> None:
    with pytest.raises(ValidationError):
        AgentObservation(
            kind="no_practice",
            no_practice_reason_codes=sequence,
        )


def test_non_no_practice_observation_rejects_reason_codes() -> None:
    with pytest.raises(ValidationError):
        AgentObservation(
            kind="needs_generation",
            no_practice_reason_codes=["cold_start"],
        )


@pytest.mark.parametrize(
    "tool,outcome",
    [
        ("observe", "observation_classified"),
        ("generate_practice", "practice_generated"),
        ("generate_practice", "practice_resolved"),
        ("generate_practice", "generation_stale_discarded"),
        ("submit_practice", "submission_submitted"),
        ("submit_practice", "submission_reused"),
        ("submit_practice", "submission_in_progress"),
        ("submit_practice", "submission_conflict"),
        ("complete_practice", "completion_applied"),
        ("complete_practice", "completion_reused"),
    ],
)
def test_step_accepts_only_frozen_tool_outcome_pairs(
    tool: str, outcome: str
) -> None:
    step = AgentStep(tool=tool, outcome=outcome)
    assert step.tool.value == tool
    assert step.outcome.value == outcome


def test_step_rejects_cross_tool_outcome() -> None:
    with pytest.raises(ValidationError):
        AgentStep(tool="observe", outcome="submission_reused")


def test_public_response_is_strict_and_contains_no_internal_trace_fields() -> None:
    response = AgentTurnResponse(
        initial_observation=AgentObservation(kind="needs_initial_writing"),
        steps=[AgentStep(tool="observe", outcome="observation_classified")],
        final_observation=AgentObservation(kind="needs_initial_writing"),
        stop_reason="needs_initial_writing",
    )

    assert response.model_dump(mode="json") == {
        "agent_version": "writing-core-learning-agent-v1",
        "initial_observation": {
            "kind": "needs_initial_writing",
            "no_practice_reason_codes": None,
        },
        "steps": [
            {"tool": "observe", "outcome": "observation_classified"}
        ],
        "final_observation": {
            "kind": "needs_initial_writing",
            "no_practice_reason_codes": None,
        },
        "stop_reason": "needs_initial_writing",
        "current_recommendation": None,
        "current_practice": None,
    }

    for forbidden in (
        "claim_token",
        "submission_claimed_at",
        "planner_context_snapshot",
        "reasoning",
    ):
        with pytest.raises(ValidationError):
            AgentTurnResponse.model_validate(
                {
                    **response.model_dump(mode="json"),
                    forbidden: "unsafe",
                }
            )
