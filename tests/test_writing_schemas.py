"""Focused tests for Phase 2 Writing Task 2 domain boundaries."""

from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal

import pytest
from pydantic import ValidationError

from app.schemas.writing import (
    PRODUCT_BAND_INCREMENT,
    PRODUCT_BAND_INPUTS,
    PRODUCT_BAND_ROUNDING,
    PRODUCT_BAND_WEIGHTS,
    CriterionBandScores,
    StructuredProviderResult,
    WritingCriterion,
    WritingEvaluationResult,
    WritingSubmission,
    aggregate_product_band,
    count_words,
)


CRITERION_FIELDS = tuple(criterion.value for criterion in WritingCriterion)


def band_payload(value: str | Decimal) -> dict[str, Decimal]:
    return {"value": Decimal(value)}


def criterion_payload(value: str | Decimal = "6.5") -> dict[str, object]:
    return {
        "band": band_payload(value),
        "evidence": ["The response provides relevant supporting detail."],
        "feedback": "Develop this criterion with more precise examples.",
    }


def criteria_payload(
    values: tuple[str, str, str, str] = ("6.5", "6.5", "6.5", "6.5"),
) -> dict[str, object]:
    return {
        field: criterion_payload(value)
        for field, value in zip(CRITERION_FIELDS, values, strict=True)
    }


def provider_payload(
    values: tuple[str, str, str, str] = ("6.5", "6.5", "6.5", "6.5"),
) -> dict[str, object]:
    return {
        "criteria": criteria_payload(values),
        "strengths": ["The position is clear."],
        "weaknesses": ["Some support remains general."],
        "error_tags": [],
        "recommended_skills": [],
        "feedback": "Prioritize specific evidence and precise language.",
        "metadata": {
            "provider": "test-provider",
            "model": "test-model",
            "prompt_version": "writing-v1",
        },
    }


def criterion_scores(
    values: tuple[str, str, str, str],
) -> CriterionBandScores:
    return CriterionBandScores.model_validate(
        {
            field: band_payload(value)
            for field, value in zip(CRITERION_FIELDS, values, strict=True)
        }
    )


def test_valid_submission_strips_boundaries_and_counts_words() -> None:
    submission = WritingSubmission(
        question="  Discuss both views.  ",
        essay="  One  two\nthree\tfour.  ",
    )

    assert submission.question == "Discuss both views."
    assert submission.essay == "One  two\nthree\tfour."
    assert submission.word_count == 4
    assert submission.model_dump()["word_count"] == 4


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", 0),
        ("one", 1),
        ("one  two\nthree\tfour", 4),
        ("don't state-of-the-art", 2),
        ("你好 世界", 2),
        ("one\u00a0two", 2),
    ],
)
def test_word_count_uses_deterministic_unicode_whitespace_tokens(
    text: str,
    expected: int,
) -> None:
    assert count_words(text) == expected


def test_essay_below_250_words_is_valid() -> None:
    submission = WritingSubmission(
        question="To what extent do you agree?",
        essay="A short but valid response.",
    )

    assert submission.word_count == 5
    assert submission.word_count < 250


@pytest.mark.parametrize("field", ["question", "essay"])
def test_submission_rejects_blank_values(field: str) -> None:
    payload = {
        "question": "Discuss both views.",
        "essay": "A valid response.",
    }
    payload[field] = " \n\t "

    with pytest.raises(ValidationError):
        WritingSubmission.model_validate(payload)


@pytest.mark.parametrize("field", ["question", "essay"])
def test_submission_rejects_missing_fields(field: str) -> None:
    payload = {
        "question": "Discuss both views.",
        "essay": "A valid response.",
    }
    payload.pop(field)

    with pytest.raises(ValidationError):
        WritingSubmission.model_validate(payload)


def test_submission_rejects_caller_supplied_word_count() -> None:
    with pytest.raises(ValidationError, match="word_count"):
        WritingSubmission.model_validate(
            {
                "question": "Discuss both views.",
                "essay": "Only application code counts these words.",
                "word_count": 999,
            }
        )


@pytest.mark.parametrize("value", ["0", "0.5", "8.5", "9"])
def test_all_criterion_bands_accept_ielts_boundaries(value: str) -> None:
    result = StructuredProviderResult.model_validate(
        provider_payload((value, value, value, value))
    )

    assert {
        getattr(result.criteria, field).band.value for field in CRITERION_FIELDS
    } == {Decimal(value)}


@pytest.mark.parametrize("field", CRITERION_FIELDS)
@pytest.mark.parametrize("value", ["-0.5", "5.25", "5.3", "9.5"])
def test_every_criterion_rejects_invalid_band_values(
    field: str,
    value: str,
) -> None:
    payload = provider_payload()
    payload["criteria"][field]["band"] = band_payload(value)

    with pytest.raises(ValidationError):
        StructuredProviderResult.model_validate(payload)


@pytest.mark.parametrize("field", CRITERION_FIELDS)
def test_provider_result_rejects_missing_criterion(field: str) -> None:
    payload = provider_payload()
    payload["criteria"].pop(field)

    with pytest.raises(ValidationError):
        StructuredProviderResult.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    [
        "criteria",
        "strengths",
        "weaknesses",
        "error_tags",
        "recommended_skills",
        "feedback",
        "metadata",
    ],
)
def test_provider_result_rejects_missing_required_fields(field: str) -> None:
    payload = provider_payload()
    payload.pop(field)

    with pytest.raises(ValidationError):
        StructuredProviderResult.model_validate(payload)


@pytest.mark.parametrize("field", ["strengths", "weaknesses"])
def test_provider_result_requires_non_empty_summary_lists(field: str) -> None:
    payload = provider_payload()
    payload[field] = []

    with pytest.raises(ValidationError):
        StructuredProviderResult.model_validate(payload)


def test_criterion_requires_non_empty_evidence() -> None:
    payload = provider_payload()
    payload["criteria"]["task_response"]["evidence"] = []

    with pytest.raises(ValidationError):
        StructuredProviderResult.model_validate(payload)


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("criteria", "feedback"),
        ("metadata", "provider"),
        ("metadata", "model"),
        ("metadata", "prompt_version"),
    ],
)
def test_provider_result_rejects_blank_nested_text(
    section: str,
    field: str,
) -> None:
    payload = provider_payload()
    if section == "criteria":
        payload[section]["task_response"][field] = " "
    else:
        payload[section][field] = " "

    with pytest.raises(ValidationError):
        StructuredProviderResult.model_validate(payload)


@pytest.mark.parametrize("field", ["error_tags", "recommended_skills"])
def test_optional_taxonomy_items_must_be_non_blank(field: str) -> None:
    payload = provider_payload()
    payload[field] = [" "]

    with pytest.raises(ValidationError):
        StructuredProviderResult.model_validate(payload)


def test_mutable_collection_values_are_isolated() -> None:
    first = StructuredProviderResult.model_validate(provider_payload())
    second = StructuredProviderResult.model_validate(provider_payload())

    first.error_tags.append("article-use")
    first.recommended_skills.append("sentence variety")

    assert second.error_tags == []
    assert second.recommended_skills == []


def test_structured_provider_result_cannot_supply_product_band() -> None:
    payload = provider_payload()
    payload["product_band"] = band_payload("9")

    with pytest.raises(ValidationError, match="product_band"):
        StructuredProviderResult.model_validate(payload)


def test_evaluation_result_serializes_computed_product_band_and_metadata() -> None:
    result = WritingEvaluationResult.model_validate(
        {
            **provider_payload(("6", "6.5", "7", "6.5")),
            "word_count": 4,
        }
    )

    dumped = result.model_dump()

    assert result.product_band.value == Decimal("6.5")
    assert dumped["product_band"] == {"value": Decimal("6.5")}
    assert dumped["metadata"] == {
        "provider": "test-provider",
        "model": "test-model",
        "prompt_version": "writing-v1",
    }


def test_evaluation_result_rejects_provider_product_band_override() -> None:
    payload = {
        **provider_payload(("5", "5", "5", "5")),
        "word_count": 4,
        "product_band": band_payload("9"),
    }

    with pytest.raises(ValidationError, match="product_band"):
        WritingEvaluationResult.model_validate(payload)


def test_evaluation_result_requires_positive_deterministic_word_count() -> None:
    with pytest.raises(ValidationError, match="word_count"):
        WritingEvaluationResult.model_validate(
            {
                **provider_payload(),
                "word_count": 0,
            }
        )


def test_aggregation_policy_is_explicit_and_equal_weighted() -> None:
    assert PRODUCT_BAND_INPUTS == tuple(WritingCriterion)
    assert set(PRODUCT_BAND_WEIGHTS) == set(WritingCriterion)
    assert set(PRODUCT_BAND_WEIGHTS.values()) == {Decimal("0.25")}
    assert sum(PRODUCT_BAND_WEIGHTS.values(), start=Decimal("0")) == Decimal("1")
    assert PRODUCT_BAND_INCREMENT == Decimal("0.5")
    assert PRODUCT_BAND_ROUNDING == ROUND_HALF_UP

    score = aggregate_product_band(criterion_scores(("5", "6", "7", "8")))

    assert score.value == Decimal("6.5")


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (("0", "0", "0", "0"), "0"),
        (("9", "9", "9", "9"), "9"),
        (("6", "6", "6", "6.5"), "6"),
        (("6", "6", "6.5", "6.5"), "6.5"),
        (("6.5", "6.5", "6.5", "7"), "6.5"),
        (("6.5", "6.5", "7", "7"), "7"),
        (("0", "0", "0", "0.5"), "0"),
        (("0", "0", "0.5", "0.5"), "0.5"),
        (("8.5", "8.5", "9", "9"), "9"),
    ],
)
def test_aggregation_rounding_ties_and_boundaries(
    values: tuple[str, str, str, str],
    expected: str,
) -> None:
    score = aggregate_product_band(criterion_scores(values))

    assert score.value == Decimal(expected)
    assert score.value % PRODUCT_BAND_INCREMENT == 0


@pytest.mark.parametrize("half_band_unit_total", range(73))
def test_aggregation_covers_every_reachable_weighted_mean(
    half_band_unit_total: int,
) -> None:
    remaining = half_band_unit_total
    half_band_units: list[int] = []
    for _ in CRITERION_FIELDS:
        criterion_units = min(remaining, 18)
        half_band_units.append(criterion_units)
        remaining -= criterion_units

    values = tuple(str(Decimal(units) / 2) for units in half_band_units)
    raw_mean = Decimal(half_band_unit_total) / 8
    expected = (raw_mean / PRODUCT_BAND_INCREMENT).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    ) * PRODUCT_BAND_INCREMENT

    score = aggregate_product_band(criterion_scores(values))

    assert remaining == 0
    assert score.value == expected


@pytest.mark.parametrize("field", CRITERION_FIELDS)
def test_aggregation_rejects_missing_inputs(field: str) -> None:
    payload = {
        criterion: band_payload("6.5")
        for criterion in CRITERION_FIELDS
        if criterion != field
    }

    with pytest.raises(ValidationError):
        CriterionBandScores.model_validate(payload)


@pytest.mark.parametrize("value", ["-0.5", "5.25", "5.3", "9.5"])
def test_aggregation_rejects_invalid_input_precision_and_range(value: str) -> None:
    payload = {
        criterion: band_payload("6.5")
        for criterion in CRITERION_FIELDS
    }
    payload["task_response"] = band_payload(value)

    with pytest.raises(ValidationError):
        CriterionBandScores.model_validate(payload)


def test_provider_validation_does_not_mutate_input() -> None:
    payload = provider_payload()
    original = deepcopy(payload)

    StructuredProviderResult.model_validate(payload)

    assert payload == original
