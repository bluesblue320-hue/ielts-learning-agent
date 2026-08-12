"""Atomic persistence for validated Writing Task 2 evaluations."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import WritingAttempt, WritingEvaluation
from app.schemas.writing import (
    WritingCriterion,
    WritingEvaluationResult,
    WritingSubmission,
)


@dataclass(frozen=True, slots=True)
class PersistedWritingEvaluation:
    """Identifiers returned only after the transaction commits."""

    attempt_id: int
    evaluation_id: int


class WritingPersistenceError(RuntimeError):
    """Safe application error for any failed writing transaction."""


class WritingEvaluationPersistenceService:
    """Persist one attempt/evaluation pair in one explicit transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def persist(
        self,
        submission: WritingSubmission,
        evaluation: WritingEvaluationResult,
    ) -> PersistedWritingEvaluation:
        validated_submission = self._validated_submission(submission)
        validated_evaluation = self._validated_evaluation(evaluation)
        if validated_evaluation.word_count != validated_submission.word_count:
            raise ValueError(
                "evaluation word_count must match the deterministic submission "
                "word count"
            )

        attempt = WritingAttempt(
            question=validated_submission.question,
            essay=validated_submission.essay,
            word_count=validated_submission.word_count,
        )
        evaluation_record = self._evaluation_record(validated_evaluation)
        attempt.evaluation = evaluation_record

        try:
            with self._session.begin():
                self._session.add(attempt)
                self._session.flush()
                attempt_id = attempt.id
                evaluation_id = evaluation_record.id
        except SQLAlchemyError as error:
            self._session.rollback()
            raise WritingPersistenceError(
                "Writing evaluation could not be persisted."
            ) from error

        return PersistedWritingEvaluation(
            attempt_id=attempt_id,
            evaluation_id=evaluation_id,
        )

    @staticmethod
    def _validated_submission(value: WritingSubmission) -> WritingSubmission:
        payload: Any = value
        if isinstance(value, WritingSubmission):
            payload = value.model_dump(exclude={"word_count"})
        return WritingSubmission.model_validate(payload)

    @staticmethod
    def _validated_evaluation(
        value: WritingEvaluationResult,
    ) -> WritingEvaluationResult:
        payload: Any = value
        if isinstance(value, WritingEvaluationResult):
            payload = value.model_dump(exclude={"product_band"})
        return WritingEvaluationResult.model_validate(payload)

    @staticmethod
    def _evaluation_record(
        evaluation: WritingEvaluationResult,
    ) -> WritingEvaluation:
        criteria_feedback = {
            criterion.value: {
                "evidence": list(
                    getattr(evaluation.criteria, criterion.value).evidence
                ),
                "feedback": getattr(
                    evaluation.criteria,
                    criterion.value,
                ).feedback,
            }
            for criterion in WritingCriterion
        }
        return WritingEvaluation(
            task_response_band=evaluation.criteria.task_response.band.value,
            coherence_and_cohesion_band=(
                evaluation.criteria.coherence_and_cohesion.band.value
            ),
            lexical_resource_band=(
                evaluation.criteria.lexical_resource.band.value
            ),
            grammatical_range_and_accuracy_band=(
                evaluation.criteria.grammatical_range_and_accuracy.band.value
            ),
            product_band=evaluation.product_band.value,
            criteria_feedback=criteria_feedback,
            strengths=list(evaluation.strengths),
            weaknesses=list(evaluation.weaknesses),
            error_tags=list(evaluation.error_tags),
            recommended_skills=list(evaluation.recommended_skills),
            feedback=evaluation.feedback,
            provider=evaluation.metadata.provider,
            model=evaluation.metadata.model,
            prompt_version=evaluation.metadata.prompt_version,
        )
