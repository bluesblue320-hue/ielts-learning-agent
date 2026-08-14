"""Focused tests for P3-06 Writing evidence extraction."""

import inspect
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.learner.writing_evidence import (
    ExtractedWritingEvidence,
    ExtractedWritingEvidenceSet,
    WritingEvidenceExtractionError,
    extract_writing_evidence,
)
from app.learner.writing_policy import WRITING_SKILLS
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.common import BandScore

T1 = datetime(2026, 1, 10, 9, 30, tzinfo=timezone.utc)
T2 = datetime(2026, 1, 12, 18, 45, tzinfo=timezone.utc)

DEFAULT_BANDS = {
    "task_response": Decimal("6.0"),
    "coherence_and_cohesion": Decimal("6.5"),
    "lexical_resource": Decimal("7.0"),
    "grammatical_range_and_accuracy": Decimal("7.5"),
}


def make_attempt(attempt_id: int = 101, created_at: datetime = T1) -> WritingAttempt:
    return WritingAttempt(
        id=attempt_id,
        question="Should cities invest more in public transport?",
        essay="A clear and reasoned response with examples.",
        word_count=8,
        created_at=created_at,
    )


def make_evaluation(
    evaluation_id: int = 201,
    attempt_id: int = 101,
    bands: dict[str, Decimal] | None = None,
    created_at: datetime = T2,
    provider: str = "deepseek",
    model: str = "deepseek-chat",
    prompt_version: str = "writing-v2",
    rubric_version: str = "writing-task2-v1",
    scoring_policy_version: str = "writing-scoring-v1",
    thinking_mode: str = "disabled",
    free_text_variant: bool = False,
) -> WritingEvaluation:
    if bands is None:
        bands = DEFAULT_BANDS
    if free_text_variant:
        criteria_feedback: dict[str, Any] = {
            "task_response": {"evidence": ["different reasoning"]}
        }
        strengths = ["different strengths"]
        weaknesses = ["different weaknesses"]
        error_tags = ["other-error"]
        recommended_skills = ["other-skill"]
        feedback = "A completely different feedback text."
    else:
        criteria_feedback = {"task_response": {"evidence": ["clearly addressed"]}}
        strengths = ["clear structure"]
        weaknesses = ["occasional repetition"]
        error_tags = ["wordiness"]
        recommended_skills = ["expand vocabulary"]
        feedback = "Good response with a clear position."
    return WritingEvaluation(
        id=evaluation_id,
        attempt_id=attempt_id,
        task_response_band=bands["task_response"],
        coherence_and_cohesion_band=bands["coherence_and_cohesion"],
        lexical_resource_band=bands["lexical_resource"],
        grammatical_range_and_accuracy_band=bands["grammatical_range_and_accuracy"],
        product_band=Decimal("6.5"),
        criteria_feedback=criteria_feedback,
        strengths=strengths,
        weaknesses=weaknesses,
        error_tags=error_tags,
        recommended_skills=recommended_skills,
        feedback=feedback,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        rubric_version=rubric_version,
        scoring_policy_version=scoring_policy_version,
        thinking_mode=thinking_mode,
        created_at=created_at,
    )


def items_in_order(result: ExtractedWritingEvidenceSet) -> list[ExtractedWritingEvidence]:
    return [getattr(result, skill) for skill in WRITING_SKILLS]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_extracts_exactly_four_canonical_evidence_items() -> None:
    evaluation = make_evaluation()
    attempt = make_attempt()

    result = extract_writing_evidence(evaluation, attempt)

    items = items_in_order(result)
    assert len(items) == 4
    assert [item.skill for item in items] == list(WRITING_SKILLS)

    expected_bands = {
        "task_response": Decimal("6.0"),
        "coherence_and_cohesion": Decimal("6.5"),
        "lexical_resource": Decimal("7.0"),
        "grammatical_range_and_accuracy": Decimal("7.5"),
    }
    for item in items:
        assert isinstance(item.observed_band, BandScore)
        assert isinstance(item.observed_band.value, Decimal)
        assert item.observed_band.value == expected_bands[item.skill]
        assert item.writing_evaluation_id == 201
        assert item.source_created_at == T1
        assert item.source_attempt_id == 101
        assert item.provenance.provider == "deepseek"
        assert item.provenance.model == "deepseek-chat"
        assert item.provenance.prompt_version == "writing-v2"
        assert item.provenance.rubric_version == "writing-task2-v1"
        assert item.provenance.scoring_policy_version == "writing-scoring-v1"
        assert item.provenance.thinking_mode == "disabled"


# ---------------------------------------------------------------------------
# Canonical cross-evaluation order source
# ---------------------------------------------------------------------------


def test_uses_attempt_created_at_not_evaluation_created_at() -> None:
    assert T1 != T2
    evaluation = make_evaluation(created_at=T2)
    attempt = make_attempt(created_at=T1)

    result = extract_writing_evidence(evaluation, attempt)

    for item in items_in_order(result):
        assert item.source_created_at == T1
        assert item.source_attempt_id == 101


def test_preserves_attempt_id_tie_break_for_equal_created_at() -> None:
    same_created_at = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    first = extract_writing_evidence(
        make_evaluation(attempt_id=100),
        make_attempt(attempt_id=100, created_at=same_created_at),
    )
    second = extract_writing_evidence(
        make_evaluation(attempt_id=101),
        make_attempt(attempt_id=101, created_at=same_created_at),
    )

    for item in items_in_order(first):
        assert item.source_attempt_id == 100
        assert item.source_created_at == same_created_at
    for item in items_in_order(second):
        assert item.source_attempt_id == 101
        assert item.source_created_at == same_created_at


# ---------------------------------------------------------------------------
# Source relationship / persisted identity
# ---------------------------------------------------------------------------


def test_rejects_mismatched_attempt() -> None:
    evaluation = make_evaluation(attempt_id=100)
    attempt = make_attempt(attempt_id=101)

    with pytest.raises(WritingEvidenceExtractionError) as exc_info:
        extract_writing_evidence(evaluation, attempt)
    assert "attempt" in str(exc_info.value)
    # Error messages must not dump essay text or source payloads.
    assert "public transport" not in str(exc_info.value)


def test_rejects_missing_evaluation_id() -> None:
    evaluation = make_evaluation(evaluation_id=None)  # type: ignore[arg-type]
    attempt = make_attempt()

    with pytest.raises(WritingEvidenceExtractionError, match="evaluation.id"):
        extract_writing_evidence(evaluation, attempt)


def test_rejects_missing_attempt_id() -> None:
    evaluation = make_evaluation()
    attempt = make_attempt(attempt_id=None)  # type: ignore[arg-type]

    with pytest.raises(WritingEvidenceExtractionError, match="attempt.id"):
        extract_writing_evidence(evaluation, attempt)


def test_rejects_missing_attempt_created_at() -> None:
    evaluation = make_evaluation()
    attempt = make_attempt(created_at=None)  # type: ignore[arg-type]

    with pytest.raises(WritingEvidenceExtractionError, match="created_at"):
        extract_writing_evidence(evaluation, attempt)


# ---------------------------------------------------------------------------
# Band boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0.0", "0.5", "8.5", "9.0"])
def test_valid_half_band_boundaries_accepted(value: str) -> None:
    bands = dict(DEFAULT_BANDS)
    bands["task_response"] = Decimal(value)

    result = extract_writing_evidence(
        make_evaluation(bands=bands),
        make_attempt(),
    )

    assert result.task_response.observed_band.value == Decimal(value)


@pytest.mark.parametrize("value", ["-0.5", "6.25", "9.5", "None"])
def test_invalid_band_fails_whole_extraction(value: str) -> None:
    bands = dict(DEFAULT_BANDS)
    bands["task_response"] = None if value == "None" else Decimal(value)

    with pytest.raises(WritingEvidenceExtractionError, match="observed band"):
        extract_writing_evidence(make_evaluation(bands=bands), make_attempt())


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"thinking_mode": "auto"},
        {"provider": ""},
        {"model": ""},
        {"prompt_version": ""},
        {"rubric_version": ""},
        {"scoring_policy_version": ""},
    ],
)
def test_invalid_provenance_fails_extraction(kwargs: dict[str, str]) -> None:
    evaluation = make_evaluation(**kwargs)

    with pytest.raises(WritingEvidenceExtractionError, match="provenance"):
        extract_writing_evidence(evaluation, make_attempt())


# ---------------------------------------------------------------------------
# Free-text independence and determinism
# ---------------------------------------------------------------------------


def test_free_text_fields_do_not_affect_extracted_evidence() -> None:
    base = make_evaluation()
    variant = make_evaluation(free_text_variant=True)

    result_a = extract_writing_evidence(base, make_attempt())
    result_b = extract_writing_evidence(variant, make_attempt())

    assert result_a == result_b


def test_extraction_is_deterministic() -> None:
    evaluation = make_evaluation()
    attempt = make_attempt()

    first = extract_writing_evidence(evaluation, attempt)
    second = extract_writing_evidence(evaluation, attempt)

    assert first == second


# ---------------------------------------------------------------------------
# Extraction boundary: no fake persistence/application identity
# ---------------------------------------------------------------------------


def test_output_does_not_invent_persistence_identity() -> None:
    assert set(ExtractedWritingEvidence.model_fields) == {
        "writing_evaluation_id",
        "skill",
        "observed_band",
        "source_created_at",
        "source_attempt_id",
        "provenance",
    }
    assert "learner_id" not in ExtractedWritingEvidence.model_fields
    assert "learning_update_id" not in ExtractedWritingEvidence.model_fields
    assert "id" not in ExtractedWritingEvidence.model_fields
    assert "created_at" not in ExtractedWritingEvidence.model_fields

    # Extraction succeeds without supplying any application identity.
    result = extract_writing_evidence(make_evaluation(), make_attempt())
    assert result.task_response.writing_evaluation_id == 201


def test_set_rejects_skill_field_mismatch() -> None:
    item = ExtractedWritingEvidence(
        writing_evaluation_id=201,
        skill="coherence_and_cohesion",
        observed_band=BandScore(value=Decimal("6.0")),
        source_created_at=T1,
        source_attempt_id=101,
        provenance=_default_provenance(),
    )
    payload = {
        "task_response": item,
        "coherence_and_cohesion": _build_item("coherence_and_cohesion"),
        "lexical_resource": _build_item("lexical_resource"),
        "grammatical_range_and_accuracy": _build_item(
            "grammatical_range_and_accuracy"
        ),
    }
    with pytest.raises(ValidationError, match="skill"):
        ExtractedWritingEvidenceSet.model_validate(payload)


def _default_provenance() -> Any:
    from app.schemas.writing import EvaluationMetadata

    return EvaluationMetadata(
        provider="deepseek",
        model="deepseek-chat",
        prompt_version="writing-v2",
        rubric_version="writing-task2-v1",
        scoring_policy_version="writing-scoring-v1",
        thinking_mode="disabled",
    )


def _build_item(skill: str) -> ExtractedWritingEvidence:
    return ExtractedWritingEvidence(
        writing_evaluation_id=201,
        skill=skill,
        observed_band=BandScore(value=Decimal("6.5")),
        source_created_at=T1,
        source_attempt_id=101,
        provenance=_default_provenance(),
    )


# ---------------------------------------------------------------------------
# Scope: no database / provider coupling
# ---------------------------------------------------------------------------


def test_module_has_no_database_or_provider_imports() -> None:
    import app.learner.writing_evidence as module

    source = inspect.getsource(module)
    # No SQLAlchemy/DBAPI imports or Session usage patterns.
    assert "sqlalchemy" not in source
    assert "from sqlalchemy" not in source
    for call in (
        "session.execute",
        "session.add",
        "session.flush",
        "session.commit",
        "session.refresh",
        "Session(",
    ):
        assert call not in source
    # No provider/LLM coupling and no non-determinism sources.
    assert "app.llm" not in source
    assert "datetime.now" not in source
    assert "uuid" not in source
    assert "random" not in source
