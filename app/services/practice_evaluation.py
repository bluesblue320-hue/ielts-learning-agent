"""Read the authoritative persisted evaluation for one submitted Writing practice."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.common import BandScore
from app.schemas.practice import PracticeLifecycleState
from app.schemas.writing import (
    CriterionEvaluation,
    EvaluationMetadata,
    WritingCriteria,
    WritingEvaluationResponse,
    WritingEvaluationResult,
)
from app.services.practice_completion import (
    PracticeCompletionNotFoundError,
    PracticeCompletionOwnershipError,
    PracticeCompletionPersistenceError,
    PracticeNotSubmittedError,
)


class PracticeEvaluationRetrievalService:
    """Expose only the evaluation linked through a submitted practice attempt."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, learner_id: int, practice_id: int) -> WritingEvaluationResponse:
        try:
            practice = self._session.scalar(
                select(WritingPractice).where(WritingPractice.id == practice_id)
            )
            if practice is None:
                raise PracticeCompletionNotFoundError("writing practice was not found")
            if practice.learner_id != learner_id:
                raise PracticeCompletionOwnershipError("writing practice belongs to another learner")
            if practice.lifecycle_state != PracticeLifecycleState.SUBMITTED.value:
                raise PracticeNotSubmittedError("writing practice has not been submitted")
            if practice.attempt_id is None:
                raise PracticeCompletionPersistenceError("submitted practice has no writing attempt")
            attempt = self._session.get(WritingAttempt, practice.attempt_id)
            evaluation = self._session.scalar(
                select(WritingEvaluation).where(
                    WritingEvaluation.attempt_id == practice.attempt_id
                )
            )
            if attempt is None or evaluation is None:
                raise PracticeCompletionPersistenceError(
                    "submitted practice evaluation link is incomplete"
                )
            return _response(attempt, evaluation)
        except (
            PracticeCompletionNotFoundError,
            PracticeCompletionOwnershipError,
            PracticeNotSubmittedError,
            PracticeCompletionPersistenceError,
        ):
            self._session.rollback()
            raise
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeCompletionPersistenceError(
                "writing practice evaluation persistence failure"
            ) from error


def _response(
    attempt: WritingAttempt, evaluation: WritingEvaluation
) -> WritingEvaluationResponse:
    try:
        criteria = WritingCriteria(
            task_response=_criterion(evaluation, "task_response", evaluation.task_response_band),
            coherence_and_cohesion=_criterion(
                evaluation, "coherence_and_cohesion", evaluation.coherence_and_cohesion_band
            ),
            lexical_resource=_criterion(
                evaluation, "lexical_resource", evaluation.lexical_resource_band
            ),
            grammatical_range_and_accuracy=_criterion(
                evaluation,
                "grammatical_range_and_accuracy",
                evaluation.grammatical_range_and_accuracy_band,
            ),
        )
        return WritingEvaluationResponse(
            attempt_id=attempt.id,
            evaluation_id=evaluation.id,
            evaluation=WritingEvaluationResult(
                criteria=criteria,
                strengths=list(evaluation.strengths),
                weaknesses=list(evaluation.weaknesses),
                error_tags=list(evaluation.error_tags),
                recommended_skills=list(evaluation.recommended_skills),
                feedback=evaluation.feedback,
                metadata=EvaluationMetadata(
                    provider=evaluation.provider,
                    model=evaluation.model,
                    prompt_version=evaluation.prompt_version,
                    rubric_version=evaluation.rubric_version,
                    scoring_policy_version=evaluation.scoring_policy_version,
                    thinking_mode=evaluation.thinking_mode,
                ),
                word_count=attempt.word_count,
            ),
        )
    except (KeyError, TypeError, ValueError):
        raise PracticeCompletionPersistenceError(
            "persisted writing evaluation cannot be represented"
        ) from None


def _criterion(
    evaluation: WritingEvaluation, skill: str, band: object
) -> CriterionEvaluation:
    item = evaluation.criteria_feedback[skill]
    return CriterionEvaluation(
        band=BandScore(value=band),
        evidence=list(item["evidence"]),
        feedback=item["feedback"],
    )