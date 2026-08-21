"""Claimed Phase 4 practice submission and atomic Phase 2 finalization."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.learning import Learner, LearningUpdate, PracticeRecommendation
from app.models.practice import WritingPractice
from app.models.writing import WritingEvaluation
from app.schemas.practice import PracticeLifecycleState, PracticeSubmission, SubmissionResult
from app.schemas.writing import WritingSubmission
from app.services.writing_evaluation import WritingEvaluationService
from app.services.writing_persistence import WritingEvaluationPersistenceService

SUBMISSION_CLAIM_LEASE_SECONDS = 300


@dataclass(frozen=True)
class AgentSubmissionExpectation:
    """Private freshness anchors for a first Agent-owned current submission."""

    expected_learning_update_id: int
    expected_recommendation_id: int


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

    def __init__(
        self,
        session: Session,
        evaluator: WritingEvaluationService | Callable[[], WritingEvaluationService],
    ) -> None:
        self._session = session
        self._evaluator = evaluator

    def _evaluation_service(self) -> WritingEvaluationService:
        if callable(self._evaluator):
            self._evaluator = self._evaluator()
        return self._evaluator

    async def submit(
        self,
        *,
        learner_id: int,
        practice_id: int,
        submission: PracticeSubmission,
        agent_expectation: AgentSubmissionExpectation | None = None,
    ) -> SubmissionResult:
        validated = PracticeSubmission.model_validate(submission)
        claim = self._claim(
            learner_id=learner_id,
            practice_id=practice_id,
            essay=validated.essay,
            agent_expectation=agent_expectation,
        )
        if isinstance(claim, SubmissionResult):
            return claim
        token, writing_submission = claim
        try:
            evaluation = await self._evaluation_service().evaluate(writing_submission)
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
        agent_expectation: AgentSubmissionExpectation | None = None,
    ) -> SubmissionResult | tuple[str, WritingSubmission]:
        # Release an implicit caller read transaction before the short lock scope.
        if self._session.in_transaction():
            self._session.rollback()
        try:
            with self._session.begin():
                if agent_expectation is not None:
                    # Match apply's same-learner serialization before checking the
                    # observed update/recommendation, then lock the practice.
                    learner = self._session.scalar(
                        select(Learner).where(Learner.id == learner_id).with_for_update()
                    )
                    if learner is None:
                        raise PracticeNotFoundError("writing practice was not found")
                    latest_update_id = self._session.scalar(
                        select(LearningUpdate.id)
                        .where(LearningUpdate.learner_id == learner_id)
                        .order_by(LearningUpdate.id.desc())
                        .limit(1)
                    )
                    current_recommendation = self._session.scalar(
                        select(PracticeRecommendation.id).where(
                            PracticeRecommendation.id
                            == agent_expectation.expected_recommendation_id,
                            PracticeRecommendation.learner_id == learner_id,
                            PracticeRecommendation.learning_update_id
                            == agent_expectation.expected_learning_update_id,
                        )
                    )
                    if (
                        latest_update_id != agent_expectation.expected_learning_update_id
                        or current_recommendation is None
                    ):
                        self._raise_agent_stale()
                practice = self._session.scalar(
                    select(WritingPractice)
                    .where(WritingPractice.id == practice_id)
                    .with_for_update()
                )
                if practice is None:
                    raise PracticeNotFoundError("writing practice was not found")
                if practice.learner_id != learner_id:
                    raise PracticeOwnershipError("writing practice belongs to another learner")
                if (
                    agent_expectation is not None
                    and practice.recommendation_id
                    != agent_expectation.expected_recommendation_id
                ):
                    self._raise_agent_stale()
                trusted_submission = WritingSubmission(question=practice.question, essay=essay)
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
                    if practice.submission_fingerprint != fingerprint:
                        return SubmissionResult(status="conflict")
                    if practice.submission_claimed_at is None:
                        raise PracticeSubmissionPersistenceError(
                            "in-progress writing practice has no claim timestamp"
                        )
                    database_now = self._database_now()
                    if (
                        database_now - practice.submission_claimed_at
                        < timedelta(seconds=SUBMISSION_CLAIM_LEASE_SECONDS)
                    ):
                        return SubmissionResult(status="in_progress")
                    token = secrets.token_urlsafe(32)
                    practice.claim_token = token
                    practice.submission_claimed_at = database_now
                    self._session.flush()
                    return token, trusted_submission
                token = secrets.token_urlsafe(32)
                database_now = self._database_now()
                practice.lifecycle_state = PracticeLifecycleState.SUBMISSION_IN_PROGRESS.value
                practice.submission_fingerprint = fingerprint
                practice.claim_token = token
                practice.submission_claimed_at = database_now
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

    def _database_now(self):
        """Read PostgreSQL wall-clock time after the locked practice is acquired."""

        database_now = self._session.scalar(select(func.clock_timestamp()))
        if database_now is None:  # pragma: no cover - PostgreSQL invariant
            raise PracticeSubmissionPersistenceError("database did not return a claim timestamp")
        return database_now

    @staticmethod
    def _raise_agent_stale() -> None:
        # A local import keeps the pure selector independent of persistence.
        from app.agent.selector import AgentStalePracticeError

        raise AgentStalePracticeError("agent practice submission is no longer current")

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
                    practice.submission_claimed_at = None
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeSubmissionPersistenceError(
                "writing practice claim reset could not be persisted"
            ) from error

    def _finalize(
        self, *, practice_id: int, claim_token: str, submission: WritingSubmission, evaluation
    ) -> SubmissionResult:
        if self._session.in_transaction():
            self._session.rollback()
        attempt, evaluation_record = WritingEvaluationPersistenceService.build_records(
            submission, evaluation
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
                practice.submission_claimed_at = None
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
            self._reset_claim_if_owned(practice_id=practice_id, claim_token=claim_token)
            raise PracticeSubmissionPersistenceError(
                "writing practice finalization could not be persisted"
            ) from error