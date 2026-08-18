"""P4-04 practice schema boundary tests."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.common import BandScore
from app.schemas.learner import LearnerSkillState, LearnerSkillStateSet
from app.schemas.planning import (
    DecisionType,
    PlannerReasonCode,
    PracticeRecommendationDecision,
)
from app.schemas.practice import (
    MAX_PRACTICE_ITEMS,
    MAX_PRACTICE_OBJECTIVE_CHARACTERS,
    MAX_PRACTICE_QUESTION_CHARACTERS,
    ClosedLoopResult,
    GeneratedWritingPractice,
    GenerationOutcome,
    PracticeLifecycleState,
    PracticeResponse,
    PracticeSubmission,
    SubmissionResult,
)

DT = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def generated(
    *,
    target_skill: str = "task_response",
    question: str = "Some people believe that cities should invest in public transport. To what extent do you agree?",
    focus_objective: str = "Develop a clear position on the statement.",
    instructions: list[str] | None = None,
    checkpoints: list[str] | None = None,
) -> GeneratedWritingPractice:
    return GeneratedWritingPractice(
        practice_type="task2_focus",
        target_skill=target_skill,
        question=question,
        focus_objective=focus_objective,
        instructions=instructions if instructions is not None else ["State your position clearly."],
        checkpoints=checkpoints if checkpoints is not None else ["Position stated in the introduction."],
        generator_policy_version="writing-practice-generation-v1",
        provider="deepseek",
        model="deepseek-chat",
        prompt_version="practice-generation-v1",
        thinking_mode="disabled",
    )


# ---------------------------------------------------------------------------
# PracticeSubmission is essay-only
# ---------------------------------------------------------------------------


def test_submission_carries_essay_only() -> None:
    submission = PracticeSubmission(essay="My essay text.")
    assert submission.essay == "My essay text."
    # No question field exists on the Phase 4 submission boundary.
    with pytest.raises(ValidationError):
        PracticeSubmission(essay="e", question="client supplied question")  # type: ignore[call-arg]


def test_submission_rejects_blank_essay() -> None:
    with pytest.raises(ValidationError):
        PracticeSubmission(essay="")


# ---------------------------------------------------------------------------
# GeneratedWritingPractice contract
# ---------------------------------------------------------------------------


def test_generated_practice_valid() -> None:
    practice = generated()
    assert practice.target_skill == "task_response"
    assert practice.generator_policy_version == "writing-practice-generation-v1"


def test_generated_practice_question_limit() -> None:
    with pytest.raises(ValidationError):
        generated(question="q" * (MAX_PRACTICE_QUESTION_CHARACTERS + 1))


def test_generated_practice_objective_limit() -> None:
    with pytest.raises(ValidationError):
        generated(focus_objective="o" * (MAX_PRACTICE_OBJECTIVE_CHARACTERS + 1))


def test_generated_practice_item_bounds() -> None:
    # Zero items rejected.
    with pytest.raises(ValidationError):
        generated(instructions=[], checkpoints=["c"])
    # Over-limit item count rejected.
    with pytest.raises(ValidationError):
        generated(
            instructions=[f"i{i}" for i in range(MAX_PRACTICE_ITEMS + 1)],
            checkpoints=["c"],
        )
    # Over-long item rejected.
    with pytest.raises(ValidationError):
        generated(instructions=["x" * 201], checkpoints=["c"])


def test_generated_practice_authority_mirror_field_exists() -> None:
    practice = generated(target_skill="coherence_and_cohesion")
    assert practice.target_skill == "coherence_and_cohesion"


# ---------------------------------------------------------------------------
# Lifecycle / response / outcome / submission result
# ---------------------------------------------------------------------------


def test_lifecycle_states_frozen() -> None:
    assert [s.value for s in PracticeLifecycleState] == [
        "generated",
        "submission_in_progress",
        "submitted",
    ]


def test_practice_response_shape() -> None:
    response = PracticeResponse(
        id=1,
        learner_id=1,
        recommendation_id=10,
        target_skill="task_response",
        question="Q?",
        focus_objective="Objective.",
        instructions=["a"],
        checkpoints=["b"],
        practice_type="task2_focus",
        generator_policy_version="writing-practice-generation-v1",
        provider="deepseek",
        model="deepseek-chat",
        prompt_version="practice-generation-v1",
        thinking_mode="disabled",
        lifecycle_state=PracticeLifecycleState.GENERATED,
        attempt_id=None,
        created_at=DT,
        updated_at=DT,
    )
    assert response.lifecycle_state == PracticeLifecycleState.GENERATED


def test_generation_outcome_practice_and_no_practice() -> None:
    outcome = GenerationOutcome(decision="practice", practice=None)
    assert outcome.decision == "practice"
    no_practice = GenerationOutcome(
        decision="no_practice",
        practice=None,
        no_practice_reasons=["cold_start"],
    )
    assert no_practice.no_practice_reasons == ["cold_start"]


def test_submission_result_states() -> None:
    for status in ("submitted", "reused", "conflict", "in_progress"):
        result = SubmissionResult(status=status, attempt_id=None, evaluation_id=None)
        assert result.status == status


def test_closed_loop_result_carries_next_recommendation() -> None:
    def state(learner_id: int, skill: str) -> LearnerSkillState:
        return LearnerSkillState(
            learner_id=learner_id,
            skill=skill,
            estimated_band=Decimal("6.00"),
            evidence_count=1,
            last_evidence_id=1,
            state_policy_version="writing-state-ewma-v1",
            revision=1,
            updated_at=DT,
        )

    skills = [
        "task_response",
        "coherence_and_cohesion",
        "lexical_resource",
        "grammatical_range_and_accuracy",
    ]
    snapshot = LearnerSkillStateSet(**{skill: state(1, skill) for skill in skills})
    recommendation = PracticeRecommendationDecision(
        decision_type=DecisionType.PRACTICE,
        target_skill="task_response",
        learner_target_band=BandScore(value=Decimal("7.0")),
        current_estimate=Decimal("6.00"),
        reason_codes=[
            PlannerReasonCode.LARGEST_TARGET_GAP,
            PlannerReasonCode.INSUFFICIENT_EVIDENCE,
        ],
        planner_version="writing-practice-gap-v1",
        state_snapshot=snapshot,
    )
    result = ClosedLoopResult(
        practice_id=1,
        attempt_id=100,
        evaluation_id=200,
        learning_update_id=300,
        next_recommendation_id=400,
        next_recommendation=recommendation,
    )
    assert result.next_recommendation.target_skill == "task_response"
