"""P4-08 deterministic tests for practice-generator runtime adapters."""

import asyncio
import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.llm import (
    DeepSeekPracticeGenerator,
    DeepSeekSettings,
    PracticeGenerationRequest,
    PracticeGenerator,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorContext,
    ProviderRetryPolicy,
    RetryingPracticeGenerator,
    ThinkingMode,
)
from tests.fakes import FakePracticeGenerator


pytestmark = pytest.mark.provider

API_URL = "https://api.deepseek.test/chat/completions"


def request(**overrides: object) -> PracticeGenerationRequest:
    values: dict[str, object] = {
        "recommendation_id": 10,
        "target_skill": "task_response",
        "learner_target_band": Decimal("7.0"),
        "reason_codes": ["largest_target_gap"],
        "planner_version": "writing-practice-gap-v1",
        "generator_policy_version": "writing-practice-generation-v1",
        "prompt_version": "practice-generation-v1",
    }
    values.update(overrides)
    return PracticeGenerationRequest(**values)


def settings() -> DeepSeekSettings:
    return DeepSeekSettings(
        api_key="test-key",
        api_url=API_URL,
        model="test-practice-model",
        timeout_seconds=2,
        _env_file=None,
    )


def content_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "practice_type": "task2_targeted_focus",
        "target_skill": "task_response",
        "question": "Some people believe public transport should receive more funding. To what extent do you agree?",
        "focus_objective": "Develop and support a clear position.",
        "instructions": ["State your position clearly."],
        "checkpoints": ["All parts of the question are addressed."],
    }
    payload.update(overrides)
    return payload


def completion(payload: object, *, status_code: int = 200) -> httpx.Response:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        status_code,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": content},
                }
            ]
        },
        headers={"x-request-id": "practice-request-1"},
    )


def run_generator(handler: Any, *, generated_request: PracticeGenerationRequest | None = None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await DeepSeekPracticeGenerator(settings(), client=client).generate_practice(
                generated_request or request()
            )

    return asyncio.run(run())


def test_deepseek_practice_generator_uses_injected_http_and_attaches_provenance() -> None:
    captured: dict[str, object] = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(http_request.content)
        assert http_request.headers["authorization"] == "Bearer test-key"
        return completion(content_payload())

    practice = run_generator(handler)

    payload = captured["payload"]
    assert payload["model"] == "test-practice-model"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "disabled"}
    authority = json.loads(payload["messages"][1]["content"])
    assert authority["boundary"] == "application_owned_recommendation_authority"
    assert authority["decision_type"] == "practice"
    assert authority["target_skill"] == "task_response"
    assert "essay" not in authority
    assert practice.provider == "deepseek"
    assert practice.model == "test-practice-model"
    assert practice.prompt_version == "practice-generation-v1"
    assert practice.thinking_mode == "disabled"


def test_deepseek_practice_generator_rejects_target_skill_mismatch() -> None:
    with pytest.raises(ProviderError) as captured:
        run_generator(
            lambda _: completion(content_payload(target_skill="lexical_resource"))
        )

    assert captured.value.category is ProviderErrorCategory.INVALID_RESPONSE
    assert captured.value.context.operation == "generate_practice"


@pytest.mark.parametrize(
    "payload",
    [
        content_payload(extra="not allowed"),
        content_payload(instructions=[]),
        content_payload(question="q" * 401),
    ],
)
def test_deepseek_practice_generator_rejects_invalid_structured_content(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ProviderError) as captured:
        run_generator(lambda _: completion(payload))

    assert captured.value.category is ProviderErrorCategory.INVALID_RESPONSE


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def provider_error(category: ProviderErrorCategory) -> ProviderError:
    return ProviderError(
        category,
        "Safe practice-generator failure.",
        context=ProviderErrorContext(
            provider="fake-practice-provider",
            operation="generate_practice",
        ),
    )


@pytest.mark.parametrize(
    "category",
    [
        ProviderErrorCategory.CONFIGURATION,
        ProviderErrorCategory.AUTHENTICATION,
        ProviderErrorCategory.BILLING,
        ProviderErrorCategory.INVALID_RESPONSE,
        ProviderErrorCategory.REQUEST_REJECTED,
    ],
)
def test_retrying_practice_generator_does_not_retry_non_retryable_failures(
    category: ProviderErrorCategory,
) -> None:
    fake = FakePracticeGenerator([provider_error(category)])
    sleeper = RecordingSleeper()

    with pytest.raises(ProviderError) as captured:
        asyncio.run(RetryingPracticeGenerator(fake, sleeper=sleeper).generate_practice(request()))

    assert captured.value.category is category
    assert len(fake.requests) == 1
    assert sleeper.delays == []


@pytest.mark.parametrize(
    "category",
    [
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMIT,
        ProviderErrorCategory.TRANSIENT,
    ],
)
def test_retrying_practice_generator_retries_transient_failures(
    category: ProviderErrorCategory,
) -> None:
    fake = FakePracticeGenerator([provider_error(category)])
    sleeper = RecordingSleeper()

    practice = asyncio.run(
        RetryingPracticeGenerator(fake, sleeper=sleeper).generate_practice(request())
    )

    assert practice.target_skill == "task_response"
    assert len(fake.requests) == 2
    assert fake.requests[0] == fake.requests[1]
    assert sleeper.delays == [ProviderRetryPolicy().base_delay_seconds]


def test_fake_practice_generator_is_deterministic_and_policy_valid() -> None:
    fake = FakePracticeGenerator()
    generated_request = request(target_skill="coherence_and_cohesion")

    first = asyncio.run(fake.generate_practice(generated_request))
    second = asyncio.run(fake.generate_practice(generated_request))

    assert first == second
    assert first.target_skill == "coherence_and_cohesion"
    assert first.provider == "fake-practice-provider"
    assert first.thinking_mode == ThinkingMode.DISABLED.value


def test_generator_runtime_implementations_satisfy_full_protocol() -> None:
    fake = FakePracticeGenerator()
    deepseek = DeepSeekPracticeGenerator(settings())
    retrying = RetryingPracticeGenerator(fake)

    assert isinstance(fake, PracticeGenerator)
    assert isinstance(deepseek, PracticeGenerator)
    assert isinstance(retrying, PracticeGenerator)
    assert fake.thinking_mode is ThinkingMode.DISABLED
    assert deepseek.thinking_mode is ThinkingMode.DISABLED
    assert retrying.thinking_mode is ThinkingMode.DISABLED
