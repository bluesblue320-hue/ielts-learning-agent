"""Deterministic extraction of canonical Writing learning evidence (P3-06).

P3-06 converts one persisted Phase 2 ``WritingEvaluation`` plus its persisted
``WritingAttempt`` into exactly four immutable canonical criterion-evidence
values. It copies only:

- the source evaluation identity;
- the exact four structured criterion bands;
- the immutable canonical-order source values (``WritingAttempt.created_at``
  and ``WritingAttempt.id``);
- the Phase 2 evaluation provenance.

The extractor is a pure transformation layer: it performs no database I/O, no
learner-state calculation, no planning, and no provider/LLM interaction.
Persistence/application identity such as ``learner_id``, ``learning_update_id``,
evidence ``id``, and ``created_at`` is deliberately NOT invented here; P3-10
owns application orchestration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.learner.writing_policy import WRITING_SKILLS
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.common import BandScore
from app.schemas.learner import WritingSkillKey
from app.schemas.writing import EvaluationMetadata


class WritingEvidenceExtractionError(ValueError):
    """Raised when persisted Phase 2 source data cannot produce canonical
    evidence.

    Messages identify the violated invariant only; they never dump essay text
    or large source payloads.
    """


# Frozen mapping from canonical P3-02 skill key to the persisted Phase 2
# criterion-band column on WritingEvaluation. There are exactly four entries
# and no alias such as grammar/vocabulary/task.
_CRITERION_BAND_ATTRIBUTES: Final[dict[str, str]] = {
    "task_response": "task_response_band",
    "coherence_and_cohesion": "coherence_and_cohesion_band",
    "lexical_resource": "lexical_resource_band",
    "grammatical_range_and_accuracy": "grammatical_range_and_accuracy_band",
}


def _require_persisted_positive_id(value: object, field: str) -> int:
    """Return a positive persisted integer identity or fail extraction."""
    if value is None or value <= 0:
        raise WritingEvidenceExtractionError(
            f"source {field} must be a positive persisted id"
        )
    return value


def _validate_sources(
    evaluation: WritingEvaluation,
    attempt: WritingAttempt,
) -> None:
    """Validate persisted source identity and the evaluation-attempt link."""
    _require_persisted_positive_id(evaluation.id, "evaluation.id")
    _require_persisted_positive_id(evaluation.attempt_id, "evaluation.attempt_id")
    _require_persisted_positive_id(attempt.id, "attempt.id")
    if attempt.created_at is None:
        raise WritingEvidenceExtractionError(
            "source attempt must expose a persisted created_at"
        )
    if evaluation.attempt_id != attempt.id:
        raise WritingEvidenceExtractionError(
            f"evaluation.attempt_id {evaluation.attempt_id} "
            f"does not match attempt.id {attempt.id}"
        )


class ExtractedWritingEvidence(BaseModel):
    """One immutable canonical criterion observation owned by P3-06.

    This is the extraction boundary: it carries only facts the extractor
    genuinely owns. Persistence/application identity (``learner_id``,
    ``learning_update_id``, evidence ``id``, ``created_at``) is deliberately
    absent; P3-10 combines these extracted values with application-owned
    identity when persisting ``LearningEvidence``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    writing_evaluation_id: int = Field(gt=0)
    skill: WritingSkillKey
    observed_band: BandScore
    # Immutable canonical-order source values copied from WritingAttempt.
    source_created_at: datetime
    source_attempt_id: int = Field(gt=0)
    provenance: EvaluationMetadata


class ExtractedWritingEvidenceSet(BaseModel):
    """Exactly four canonical extracted evidence values, keyed by skill.

    All four items must describe the same logical evaluation: they must share
    the evaluation identity, the canonical-order source values, and the Phase
    2 provenance. Inconsistent input is rejected, never normalized.
    """

    model_config = ConfigDict(extra="forbid")

    task_response: ExtractedWritingEvidence
    coherence_and_cohesion: ExtractedWritingEvidence
    lexical_resource: ExtractedWritingEvidence
    grammatical_range_and_accuracy: ExtractedWritingEvidence

    @model_validator(mode="after")
    def _check_consistency(self) -> "ExtractedWritingEvidenceSet":
        for skill in WRITING_SKILLS:
            item = getattr(self, skill)
            if item.skill != skill:
                raise ValueError(f"evidence under {skill!r} has skill {item.skill!r}")

        first = getattr(self, WRITING_SKILLS[0])
        for skill in WRITING_SKILLS:
            item = getattr(self, skill)
            if item.writing_evaluation_id != first.writing_evaluation_id:
                raise ValueError(
                    f"evidence under {skill!r} has mismatched writing_evaluation_id"
                )
            if item.source_created_at != first.source_created_at:
                raise ValueError(
                    f"evidence under {skill!r} has mismatched source_created_at"
                )
            if item.source_attempt_id != first.source_attempt_id:
                raise ValueError(
                    f"evidence under {skill!r} has mismatched source_attempt_id"
                )
            if item.provenance != first.provenance:
                raise ValueError(f"evidence under {skill!r} has mismatched provenance")
        return self


def extract_writing_evidence(
    evaluation: WritingEvaluation,
    attempt: WritingAttempt,
) -> ExtractedWritingEvidenceSet:
    """Extract exactly four canonical criterion-evidence values.

    The caller supplies the persisted evaluation and its matching persisted
    attempt as explicit arguments; the extractor never loads anything from a
    database and never opens a Session. Extraction is all-or-nothing: a single
    missing, invalid, or non-half-band criterion fails the whole extraction.
    """

    _validate_sources(evaluation, attempt)

    try:
        provenance = EvaluationMetadata(
            provider=evaluation.provider,
            model=evaluation.model,
            prompt_version=evaluation.prompt_version,
            rubric_version=evaluation.rubric_version,
            scoring_policy_version=evaluation.scoring_policy_version,
            thinking_mode=evaluation.thinking_mode,
        )
    except ValidationError as exc:
        raise WritingEvidenceExtractionError(
            "persisted evaluation provenance is invalid"
        ) from exc

    items: dict[str, ExtractedWritingEvidence] = {}
    for skill in WRITING_SKILLS:
        band_value = getattr(evaluation, _CRITERION_BAND_ATTRIBUTES[skill])
        try:
            observed_band = BandScore(value=band_value)
        except ValidationError as exc:
            raise WritingEvidenceExtractionError(
                f"observed band for skill {skill!r} is not a valid IELTS half-band"
            ) from exc
        items[skill] = ExtractedWritingEvidence(
            writing_evaluation_id=evaluation.id,
            skill=skill,
            observed_band=observed_band,
            source_created_at=attempt.created_at,
            source_attempt_id=attempt.id,
            provenance=provenance,
        )

    return ExtractedWritingEvidenceSet(**items)
