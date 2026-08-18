"""Claimed Phase 4 practice submission and atomic Phase 2 finalization."""

from __future__ import annotations

import hashlib
import json
import secrets

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.practice import WritingPractice
from app.models.writing import WritingEvaluation
from app.schemas.practice import PracticeLifecycleState, PracticeSubmission, SubmissionResult
from app.schemas.writing import WritingSubmission
from app.services.writing_evaluation import WritingEvaluationService
from app.services.writing_persistence import WritingEvaluationPersistenceService


class PracticeSubmissionError(Exception):
    """Base error for Phase 4 practice submission outcomes."""


class PracticeNotFoundError(PracticeSubmissionError):
    """The requested practice does not exist."""


class PracticeOwnershipError(PracticeSubmissionError):
    """The requested practice belongs to another learner."""


class PracticeSubmissionPersistenceError(PracticeSubmissionError):
    """A claim/finalization database operation failed unexpectedly."""


def submission_fingerprint(*, practice_id: int, question: str, essay: str) -> str:
    """Hash the authoritative validated submission representation."""

    payload = json.dumps(
        {"essay": essay, "practice_id": practice_id, "question": question},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PracticeSubmissionService:
    """Claim a generated practice, evaluate outside the DB, then finalize once."""

    def __init__(self, session: Session, evaluator: WritingEvaluationService) -> None:
        self._session = session
        self._evaluator = evaluator

    async def submit(
        self,
        *,
        learner_id: int,
        practice_id: int,
        submission: PracticeSubmission,
    ) -> SubmissionResult:
        validated = PracticeSubmission.model_validate(submission)
        claim = self._claim(
            learner_id=learner_id,
            practice_id=practice_id,
            essay=validated.essay,
        )
        if isinstance(claim, SubmissionResult):
            return claim
        token, writing_submission = claim
        try:
            evaluation = await self._evaluator.evaluate(writing_submission)
        except Exception:
            self._reset_claim_if_owned(practice_id=practice_id, claim_token=token)
            raise
        return self._finalize(
            practice_id=practice_id,
            claim_token=token,
            submission=writing_submission,
            evaluation=evaluation,
        )

    def _claim(
        self,
        *,
        learner_id: int,
        practice_id: int,
        essay: str,
    ) -> SubmissionResult | tuple[str, WritingSubmission]:
        # The service owns the short claim transaction. Release an implicit
        # caller read transaction before acquiring the PostgreSQL row lock.
        if self._session.in_transaction():
            self._session.rollback()
        try:
            with self._session.begin():
                practice = self._session.scalar(
                    select(WritingPractice)
                    .where(WritingPractice.id == practice_id)
                    .with_for_update()
                )
                if practice is None:
                    raise PracticeNotFoundError("writing practice was not found")
                if practice.learner_id != learner_id:
                    raise PracticeOwnershipError("writing practice belongs to another learner")
                trusted_submission = WritingSubmission(
                    question=practice.question,
                    essay=essay,
                )
                fingerprint = submission_fingerprint(
                    practice_id=practice.id,
                    question=trusted_submission.question,
                    essay=trusted_submission.essay,
                )
                if practice.lifecycle_state == PracticeLifecycleState.SUBMITTED.value:
                    if practice.submission_fingerprint != fingerprint:
                        return SubmissionResult(status="conflict")
                    evaluation = self._session.scalar(
                        select(WritingEvaluation).where(
                            WritingEvaluation.attempt_id == practice.attempt_id
                        )
                    )
                    if evaluation is None or practice.attempt_id is None:
                        raise PracticeSubmissionPersistenceError(
                            "submitted practice has no evaluation"
                        )
                    return SubmissionResult(
                        status="reused",
                        attempt_id=practice.attempt_id,
                        evaluation_id=evaluation.id,
                    )
                if practice.lifecycle_state == PracticeLifecycleState.SUBMISSION_IN_PROGRESS.value:
                    return SubmissionResult(status="in_progress")
                token = secrets.token_urlsafe(32)
                practice.lifecycle_state = PracticeLifecycleState.SUBMISSION_IN_PROGRESS.value
                practice.submission_fingerprint = fingerprint
                practice.claim_token = token
                self._session.flush()
                return token, trusted_submission
        except PracticeSubmissionError:
            self._session.rollback()
            raise
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeSubmissionPersistenceError(
                "writing practice claim could not be persisted"
            ) from error

    def _reset_claim_if_owned(self, *, practice_id: int, claim_token: str) -> None:
        try:
            with self._session.begin():
                practice = self._session.scalar(
                    select(WritingPractice)
                    .where(WritingPractice.id == practice_id)
                    .with_for_update()
                )
                if (
                    practice is not None
                    and practice.lifecycle_state
                    == PracticeLifecycleState.SUBMISSION_IN_PROGRESS.value
                    and practice.claim_token == claim_token
                ):
                    practice.lifecycle_state = PracticeLifecycleState.GENERATED.value
                    practice.submission_fingerprint = None
                    practice.claim_token = None
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeSubmissionPersistenceError(
                "writing practice claim reset could not be persisted"
            ) from error

    def _finalize(self, *, practice_id: int, claim_token: str, submission: WritingSubmission, evaluation) -> SubmissionResult:
        attempt, evaluation_record = WritingEvaluationPersistenceService.build_records(
            submission,
            evaluation,
        )
        try:
            with self._session.begin():
                practice = self._session.scalar(
                    select(WritingPractice)
                    .where(WritingPractice.id == practice_id)
                    .with_for_update()
                )
                if (
                    practice is None
                    or practice.lifecycle_state
                    != PracticeLifecycleState.SUBMISSION_IN_PROGRESS.value
                    or practice.claim_token != claim_token
                ):
                    raise PracticeSubmissionPersistenceError(
                        "writing practice claim is no longer owned"
                    )
                self._session.add(attempt)
                self._session.flush()
                practice.attempt_id = attempt.id
                practice.lifecycle_state = PracticeLifecycleState.SUBMITTED.value
                practice.claim_token = None
                self._session.flush()
                return SubmissionResult(
                    status="submitted",
                    attempt_id=attempt.id,
                    evaluation_id=evaluation_record.id,
                )
        except PracticeSubmissionError:
            self._session.rollback()
            raise
        except SQLAlchemyError as error:
            self._session.rollback()
            # A recoverable finalization failure is not a process crash: once
            # its atomic transaction has rolled back, release only the claim
            # still owned by this caller so a later submission can retry.
            self._reset_claim_if_owned(
                practice_id=practice_id,
                claim_token=claim_token,
            )
            raise PracticeSubmissionPersistenceError(
                "writing practice finalization could not be persisted"
            ) from error
