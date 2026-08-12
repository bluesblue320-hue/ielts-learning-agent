"""Deterministic tests for the bounded provider retry policy."""

import asyncio

import pytest

from app.llm import (
    MAX_PROVIDER_ATTEMPTS,
    RETRYABLE_PROVIDER_ERRORS,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorContext,
    ProviderRetryPolicy,
    RetryingProvider,
)
from app.schemas.writing import WritingEvaluationResult, WritingSubmission
from app.services.writing_evaluation import WritingEvaluationService
from tests.fakes import FakeProvider


pytestmark = pytest.mark.provider


def provider_payload() -> dict[str, object]:
    criterion = {
        "band": {"value": "6.5"},
        "evidence": ["Relevant evidence."],
        "feedback": "Develop this criterion.",
    }
    return {
        "criteria": {
            "task_response": criterion,
            "coherence_and_cohesion": criterion,
            "lexical_resource": criterion,
            "grammatical_range_and_accuracy": criterion,
        },
        "strengths": ["Clear position."],
        "weaknesses": ["Support remains general."],
        "error_tags": [],
        "recommended_skills": ["supporting examples"],
        "feedback": "Use more precise evidence.",
        "metadata": {
            "provider": "ignored",
            "model": "ignored",
            "prompt_version": "ignored",
        },
    }


def provider_error(category: ProviderErrorCategory) -> ProviderError:
    return ProviderError(
        category,
        f"Safe {category.value} provider failure.",
        context=ProviderErrorContext(provider="fake-provider"),
    )


def evaluate(provider: RetryingProvider) -> WritingEvaluationResult:
    return asyncio.run(
        WritingEvaluationService(provider).evaluate(
            WritingSubmission(
                question="Discuss both views.",
                essay="A short but valid response.",
            )
        )
    )


@pytest.mark.parametrize("category", tuple(ProviderErrorCategory))
def test_every_established_error_category_has_deterministic_retry_behavior(
    category: ProviderErrorCategory,
) -> None:
    expected_attempts = (
        MAX_PROVIDER_ATTEMPTS if category in RETRYABLE_PROVIDER_ERRORS else 1
    )
    failure = provider_error(category)
    fake = FakeProvider([failure] * expected_attempts)

    with pytest.raises(ProviderError) as captured:
        evaluate(RetryingProvider(fake))

    assert captured.value is failure
    assert captured.value.category is category
    assert len(fake.requests) == expected_attempts
    assert len(fake.requests) <= MAX_PROVIDER_ATTEMPTS


@pytest.mark.parametrize("category", tuple(RETRYABLE_PROVIDER_ERRORS))
def test_transient_category_retries_then_succeeds_without_mutating_request(
    category: ProviderErrorCategory,
) -> None:
    fake = FakeProvider([provider_error(category), provider_payload()])

    result = evaluate(RetryingProvider(fake))

    assert result.product_band.value == 6.5
    assert len(fake.requests) == 2
    assert fake.requests[0] == fake.requests[1]
    assert fake.requests[0].untrusted_submission.essay == (
        "A short but valid response."
    )


def test_policy_can_disable_retries_with_one_attempt() -> None:
    failure = provider_error(ProviderErrorCategory.TIMEOUT)
    fake = FakeProvider([failure])

    with pytest.raises(ProviderError):
        evaluate(
            RetryingProvider(
                fake,
                ProviderRetryPolicy(max_attempts=1),
            )
        )

    assert len(fake.requests) == 1


@pytest.mark.parametrize("max_attempts", [0, MAX_PROVIDER_ATTEMPTS + 1])
def test_policy_rejects_unbounded_or_empty_attempt_counts(
    max_attempts: int,
) -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        ProviderRetryPolicy(max_attempts=max_attempts)


def test_retry_taxonomy_is_exact_and_does_not_redesign_provider_contract() -> None:
    assert RETRYABLE_PROVIDER_ERRORS == {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMIT,
        ProviderErrorCategory.TRANSIENT,
    }
    assert set(ProviderErrorCategory) == {
        ProviderErrorCategory.CONFIGURATION,
        ProviderErrorCategory.AUTHENTICATION,
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMIT,
        ProviderErrorCategory.TRANSIENT,
        ProviderErrorCategory.INVALID_RESPONSE,
        ProviderErrorCategory.REQUEST_REJECTED,
    }
