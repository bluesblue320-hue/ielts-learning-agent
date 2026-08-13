"""Typed Writing Task 2 boundaries and deterministic scoring policies."""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

from app.schemas.common import BandScore


NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
MAX_WRITING_QUESTION_CHARACTERS: Final[int] = 2_000
MAX_WRITING_ESSAY_CHARACTERS: Final[int] = 20_000
WritingQuestionText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_WRITING_QUESTION_CHARACTERS,
    ),
]
WritingEssayText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_WRITING_ESSAY_CHARACTERS,
    ),
]

NonEmptyTextList = Annotated[list[NonBlankText], Field(min_length=1)]


class WritingSchema(BaseModel):
    """Strict base for Writing Task 2 API and domain boundaries."""

    model_config = ConfigDict(extra="forbid")


class WritingCriterion(StrEnum):
    """The four criterion inputs used by the Writing Task 2 product score."""

    TASK_RESPONSE = "task_response"
    COHERENCE_AND_COHESION = "coherence_and_cohesion"
    LEXICAL_RESOURCE = "lexical_resource"
    GRAMMATICAL_RANGE_AND_ACCURACY = "grammatical_range_and_accuracy"


PRODUCT_BAND_INPUTS: Final[tuple[WritingCriterion, ...]] = tuple(WritingCriterion)
PRODUCT_BAND_WEIGHTS: Final[Mapping[WritingCriterion, Decimal]] = MappingProxyType(
    {criterion: Decimal("0.25") for criterion in PRODUCT_BAND_INPUTS}
)
PRODUCT_BAND_INCREMENT: Final[Decimal] = Decimal("0.5")
PRODUCT_BAND_ROUNDING: Final[str] = ROUND_HALF_UP


def count_words(text: str) -> int:
    """Count maximal non-whitespace tokens using Python's Unicode whitespace rules."""

    return len(text.split())


class WritingSubmission(WritingSchema):
    """Validated IELTS Writing Task 2 question and essay submission."""

    question: WritingQuestionText
    essay: WritingEssayText

    @computed_field(return_type=int)
    @property
    def word_count(self) -> int:
        """Return the deterministic essay word count; no minimum is imposed."""

        return count_words(self.essay)


class CriterionEvaluation(WritingSchema):
    """Validated evidence and feedback for one writing criterion."""

    band: BandScore
    evidence: NonEmptyTextList
    feedback: NonBlankText


class WritingCriteria(WritingSchema):
    """Complete criterion-level evaluation for all four required inputs."""

    task_response: CriterionEvaluation
    coherence_and_cohesion: CriterionEvaluation
    lexical_resource: CriterionEvaluation
    grammatical_range_and_accuracy: CriterionEvaluation

    def band_scores(self) -> "CriterionBandScores":
        """Extract the four validated inputs to deterministic aggregation."""

        return CriterionBandScores(
            task_response=self.task_response.band,
            coherence_and_cohesion=self.coherence_and_cohesion.band,
            lexical_resource=self.lexical_resource.band,
            grammatical_range_and_accuracy=self.grammatical_range_and_accuracy.band,
        )


class CriterionBandScores(WritingSchema):
    """Exactly four validated IELTS half-band inputs for product aggregation."""

    task_response: BandScore
    coherence_and_cohesion: BandScore
    lexical_resource: BandScore
    grammatical_range_and_accuracy: BandScore


def aggregate_product_band(scores: CriterionBandScores) -> BandScore:
    """Return the deterministic product band for four criterion scores.

    Policy frozen for Phase 2:

    - inputs are exactly the four fields on CriterionBandScores;
    - each input is a BandScore from 0 to 9 in 0.5 increments;
    - each criterion has weight 0.25 and the formula is their weighted mean;
    - output precision is 0.5;
    - the mean is rounded to the nearest 0.5 with exact ties rounded upward;
    - 0 and 9 are valid boundaries; missing or invalid inputs fail Pydantic
      validation before this function can run.

    This is a product policy, not a claim to reproduce an official final IELTS
    Writing band. Provider output cannot supply or override the returned value.
    """

    weighted_mean = sum(
        (
            getattr(scores, criterion.value).value
            * PRODUCT_BAND_WEIGHTS[criterion]
            for criterion in PRODUCT_BAND_INPUTS
        ),
        start=Decimal("0"),
    )
    rounded_units = (weighted_mean / PRODUCT_BAND_INCREMENT).quantize(
        Decimal("1"),
        rounding=PRODUCT_BAND_ROUNDING,
    )
    return BandScore(value=rounded_units * PRODUCT_BAND_INCREMENT)


class EvaluationMetadata(WritingSchema):
    """Reproducibility identifiers owned by application composition."""

    provider: NonBlankText
    model: NonBlankText
    prompt_version: NonBlankText
    rubric_version: NonBlankText
    scoring_policy_version: NonBlankText
    thinking_mode: Literal["enabled", "disabled"]


class ProviderEvaluationPayload(WritingSchema):
    """Only qualitative fields that an evaluation provider may control."""

    criteria: WritingCriteria
    strengths: NonEmptyTextList
    weaknesses: NonEmptyTextList
    error_tags: list[NonBlankText]
    recommended_skills: list[NonBlankText]
    feedback: NonBlankText


class WritingEvaluationResult(ProviderEvaluationPayload):
    """Provider payload plus deterministic evidence and application metadata."""

    metadata: EvaluationMetadata
    word_count: int = Field(ge=1)

    @computed_field(return_type=BandScore)
    @property
    def product_band(self) -> BandScore:
        """Compute the final product band from validated criteria only."""

        return aggregate_product_band(self.criteria.band_scores())


class WritingEvaluationResponse(WritingSchema):
    """Persisted API response for one completed writing evaluation."""

    attempt_id: int = Field(gt=0)
    evaluation: WritingEvaluationResult
