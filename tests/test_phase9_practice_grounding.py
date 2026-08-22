import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.llm.deepseek import DeepSeekSettings
from app.llm.deepseek_practice import DeepSeekPracticeGenerator
from app.llm.practice_generator import (
    PracticeGenerationRequest,
    PracticeKnowledgeContext,
    PracticeKnowledgeItem,
)
from app.services.practice_generation import (
    GENERATION_POLICY_VERSION,
    KNOWLEDGE_CONTEXT_VERSION,
    PRACTICE_PROMPT_VERSION,
    PracticeGenerationService,
)
from tests.fakes import FakePracticeGenerator


def _context() -> PracticeKnowledgeContext:
    return PracticeKnowledgeContext(
        items=(
            PracticeKnowledgeItem(
                knowledge_id="writing-task-response-band-7",
                statement="Task Response requires a clear, developed response.",
                source_ids=("ielts-writing-band-descriptors-2023",),
            ),
        )
    )


def _request() -> PracticeGenerationRequest:
    return PracticeGenerationRequest(
        recommendation_id=10,
        target_skill="task_response",
        learner_target_band=Decimal("7.0"),
        reason_codes=["largest_target_gap"],
        planner_version="writing-practice-gap-memory-v2",
        generator_policy_version=GENERATION_POLICY_VERSION,
        prompt_version=PRACTICE_PROMPT_VERSION,
        knowledge_context=_context(),
    )


def test_v2_context_is_strict_bounded_and_contains_no_memory() -> None:
    request = _request()
    assert request.knowledge_context is not None
    assert (
        request.knowledge_context.knowledge_context_version == KNOWLEDGE_CONTEXT_VERSION
    )
    serialized_context = request.knowledge_context.model_dump_json()
    assert "memory" not in serialized_context.lower()
    assert "essay" not in serialized_context.lower()
    with pytest.raises(ValidationError):
        PracticeKnowledgeContext.model_validate(
            {**_context().model_dump(), "planner_context_snapshot": {}}
        )


def test_shared_generation_service_builds_grounded_v2_request() -> None:
    class Session:
        def __init__(self) -> None:
            self.rollback_calls = 0

        def rollback(self) -> None:
            self.rollback_calls += 1

    generator = FakePracticeGenerator()
    session = Session()
    recommendation = SimpleNamespace(
        id=10,
        target_skill="task_response",
        current_estimate=Decimal("6.25"),
        learner_target_band=Decimal("7.0"),
        reason_codes=["largest_target_gap"],
        planner_version="writing-practice-gap-memory-v2",
    )
    generated = asyncio.run(
        PracticeGenerationService(session, generator)._generate_outside_transaction(
            recommendation
        )
    )
    request = generator.requests[0]
    assert generated.target_skill == recommendation.target_skill
    assert request.generator_policy_version == "writing-practice-generation-v2"
    assert request.prompt_version == "practice-generation-v2"
    assert request.knowledge_context is not None
    assert request.knowledge_context.items
    assert all(
        item.knowledge_id.startswith("writing-")
        for item in request.knowledge_context.items
    )
    assert session.rollback_calls == 1


def test_deepseek_payload_marks_knowledge_as_grounding_not_authority() -> None:
    settings = DeepSeekSettings(
        api_key="test-key",
        api_url="https://api.deepseek.test/chat/completions",
        model="test-practice-model",
        timeout_seconds=2,
        _env_file=None,
    )
    payload = DeepSeekPracticeGenerator(settings)._request_payload(_request())
    system = json.loads(payload["messages"][0]["content"])
    authority = json.loads(payload["messages"][1]["content"])
    assert "trusted grounding" in system["instruction"]
    assert authority["target_skill"] == "task_response"
    assert (
        authority["knowledge_context"]["knowledge_context_version"]
        == KNOWLEDGE_CONTEXT_VERSION
    )
    assert "citation" not in payload["response_format"]
