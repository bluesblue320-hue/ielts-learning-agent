"""P4-07 PracticeGenerator contract tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.llm.practice_generator import (
    PracticeGenerationRequest,
    PracticeGenerator,
)
from app.schemas.practice import GeneratedWritingPractice


def valid_request(**overrides) -> PracticeGenerationRequest:
    values = dict(
        recommendation_id=10,
        target_skill="task_response",
        learner_target_band=Decimal("7.0"),
        reason_codes=["largest_target_gap"],
        planner_version="writing-practice-gap-v1",
        generator_policy_version="writing-practice-generation-v1",
        prompt_version="practice-generation-v1",
    )
    values.update(overrides)
    return PracticeGenerationRequest(**values)


def test_request_carries_application_authority_values() -> None:
    request = valid_request()
    assert request.target_skill == "task_response"
    assert request.recommendation_id == 10
    assert request.generator_policy_version == "writing-practice-generation-v1"


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        valid_request(essay="client text")  # type: ignore[call-arg]


def test_request_requires_recommendation_id() -> None:
    with pytest.raises(ValidationError):
        valid_request(recommendation_id=0)


def test_generator_protocol_is_async_and_provider_shaped() -> None:
    # The protocol contract surface: async generate_practice + stable names.
    assert "generate_practice" in PracticeGenerator.__dict__["__protocol_attrs__"]
    assert "provider_name" in PracticeGenerator.__dict__["__protocol_attrs__"]
    assert "model_name" in PracticeGenerator.__dict__["__protocol_attrs__"]


def test_generated_practice_validates_authority_mirror_field() -> None:
    generated = GeneratedWritingPractice(
        practice_type="task2_focus",
        target_skill="task_response",
        question="Some people think that cities should invest in public transport. To what extent do you agree?",
        focus_objective="Develop a clear position.",
        instructions=["State your position clearly."],
        checkpoints=["Position stated in the introduction."],
        generator_policy_version="writing-practice-generation-v1",
        provider="deepseek",
        model="deepseek-chat",
        prompt_version="practice-generation-v1",
        thinking_mode="disabled",
    )
    # The mirrored authority field is present and structured (service-level
    # equality with the persisted recommendation is validated at P4-09).
    assert generated.target_skill == "task_response"


def test_generated_practice_rejects_noncanonical_skill() -> None:
    with pytest.raises(ValidationError):
        GeneratedWritingPractice(
            practice_type="task2_focus",
            target_skill="speaking",  # type: ignore[arg-type]
            question="Q?",
            focus_objective="O.",
            instructions=["a"],
            checkpoints=["b"],
            generator_policy_version="writing-practice-generation-v1",
            provider="deepseek",
            model="deepseek-chat",
            prompt_version="practice-generation-v1",
            thinking_mode="disabled",
        )
