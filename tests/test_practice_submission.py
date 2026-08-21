"""P4-10 real-PostgreSQL submission-claim and atomic-finalization tests."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError

from app.llm import ProviderError, ProviderErrorCategory, ProviderErrorContext
from app.models.learning import PracticeRecommendation
from app.models.practice import WritingPractice
from app.services.learning_application import apply_writing_evaluation
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.practice import PracticeSubmission
from app.services.practice_generation import PracticeGenerationService
from app.services.practice_submission import (
    AgentSubmissionExpectation,
    PracticeSubmissionPersistenceError,
    PracticeSubmissionService,
    submission_fingerprint,
)
from app.services.writing_evaluation import WritingEvaluationService
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_practice_generation import _evaluation, _recommendation, factory, truncate


pytestmark = [pytest.mark.integration, pytest.mark.provider]


def _payload() -> dict[str, object]:
    criterion = {"band": {"value": "6.5"}, "evidence": ["Evidence."], "feedback": "Feedback."}
    return {
        "criteria": {
            "task_response": criterion,
            "coherence_and_cohesion": criterion,
            "lexical_resource": criterion,
            "grammatical_range_and_accuracy": criterion,
        },
        "strengths": ["Strength."],
        "weaknesses": ["Weakness."],
        "error_tags": [],
        "recommended_skills": [],
        "feedback": "Overall feedback.",
    }


def _generated_practice(session) -> WritingPractice:
    recommendation = _recommendation(session)
    outcome = asyncio.run(
        PracticeGenerationService(session, FakePracticeGenerator()).generate_or_resolve(
            learner_id=1, recommendation_id=recommendation.id
        )
    )
    assert outcome.practice is not None
    practice = session.get(WritingPractice, outcome.practice.id)
    assert practice is not None
    return practice


def test_first_submission_uses_persisted_question_and_finalizes_atomically(factory) -> None:
    provider = FakeProvider([_payload()])
    with factory() as session:
        practice = _generated_practice(session)
        result = asyncio.run(
            PracticeSubmissionService(session, WritingEvaluationService(provider)).submit(
                learner_id=1,
                practice_id=practice.id,
                submission=PracticeSubmission(essay="Validated learner essay."),
            )
        )
        session.rollback()
        stored = session.get(WritingPractice, practice.id)
        assert result.status == "submitted"
        assert result.attempt_id is not None and result.evaluation_id is not None
        assert stored is not None
        assert stored.lifecycle_state == "submitted"
        assert stored.attempt_id == result.attempt_id
        assert stored.claim_token is None
        assert provider.requests[0].untrusted_submission.question == stored.question
        assert provider.requests[0].untrusted_submission.essay == "Validated learner essay."
        assert session.scalar(select(func.count()).select_from(WritingAttempt)) == 2
        assert session.scalar(select(func.count()).select_from(WritingEvaluation)) == 2


def test_same_fingerprint_reuses_result_without_second_provider_call(factory) -> None:
    provider = FakeProvider([_payload()])
    with factory() as session:
        practice = _generated_practice(session)
        service = PracticeSubmissionService(session, WritingEvaluationService(provider))
        first = asyncio.run(service.submit(learner_id=1, practice_id=practice.id, submission=PracticeSubmission(essay="Same essay.")))
        second = asyncio.run(service.submit(learner_id=1, practice_id=practice.id, submission=PracticeSubmission(essay="Same essay.")))
        assert first.status == "submitted"
        assert second.status == "reused"
        assert second.attempt_id == first.attempt_id
        assert second.evaluation_id == first.evaluation_id
        assert len(provider.requests) == 1


def test_different_essay_conflicts_without_second_provider_call(factory) -> None:
    provider = FakeProvider([_payload()])
    with factory() as session:
        practice = _generated_practice(session)
        service = PracticeSubmissionService(session, WritingEvaluationService(provider))
        asyncio.run(service.submit(learner_id=1, practice_id=practice.id, submission=PracticeSubmission(essay="First essay.")))
        conflict = asyncio.run(service.submit(learner_id=1, practice_id=practice.id, submission=PracticeSubmission(essay="Different essay.")))
        assert conflict.status == "conflict"
        assert len(provider.requests) == 1


def test_provider_failure_resets_owned_claim_without_orphan_writes(factory) -> None:
    failure = ProviderError(
        ProviderErrorCategory.TIMEOUT,
        "Safe timeout.",
        context=ProviderErrorContext(provider="fake-provider"),
    )
    provider = FakeProvider([failure])
    with factory() as session:
        practice = _generated_practice(session)
        with pytest.raises(ProviderError):
            asyncio.run(
                PracticeSubmissionService(session, WritingEvaluationService(provider)).submit(
                    learner_id=1,
                    practice_id=practice.id,
                    submission=PracticeSubmission(essay="Essay."),
                )
            )
        session.rollback()
        stored = session.get(WritingPractice, practice.id)
        assert stored is not None
        assert stored.lifecycle_state == "generated"
        assert stored.claim_token is None
        assert stored.submission_fingerprint is None
        assert session.scalar(select(func.count()).select_from(WritingAttempt)) == 1
        assert session.scalar(select(func.count()).select_from(WritingEvaluation)) == 1


def test_existing_in_progress_claim_does_not_evaluate_again(factory) -> None:
    provider = FakeProvider([_payload()])
    with factory() as session:
        practice = _generated_practice(session)
        practice.lifecycle_state = "submission_in_progress"
        practice.claim_token = "opaque-claim"
        practice.submission_fingerprint = submission_fingerprint(
            practice_id=practice.id, question=practice.question, essay="Essay."
        )
        practice.submission_claimed_at = session.scalar(select(func.current_timestamp()))
        session.commit()
        result = asyncio.run(
            PracticeSubmissionService(session, WritingEvaluationService(provider)).submit(
                learner_id=1,
                practice_id=practice.id,
                submission=PracticeSubmission(essay="Essay."),
            )
        )
        assert result.status == "in_progress"
        assert not provider.requests


def test_expired_matching_claim_is_reclaimed_and_finalizes_once(factory) -> None:
    provider = FakeProvider([_payload()])
    with factory() as session:
        practice = _generated_practice(session)
        essay = "Expired matching essay."
        practice.lifecycle_state = "submission_in_progress"
        practice.claim_token = "stale-owner-token"
        practice.submission_fingerprint = submission_fingerprint(
            practice_id=practice.id, question=practice.question, essay=essay
        )
        now = session.scalar(select(func.current_timestamp()))
        assert now is not None
        practice.submission_claimed_at = now - timedelta(seconds=301)
        session.commit()

        result = asyncio.run(
            PracticeSubmissionService(session, WritingEvaluationService(provider)).submit(
                learner_id=1,
                practice_id=practice.id,
                submission=PracticeSubmission(essay=essay),
            )
        )
        assert result.status == "submitted"
        assert len(provider.requests) == 1
        session.rollback()
        stored = session.get(WritingPractice, practice.id)
        assert stored is not None
        assert stored.lifecycle_state == "submitted"
        assert stored.claim_token is None
        assert stored.submission_claimed_at is None
        assert session.scalar(select(func.count()).select_from(WritingAttempt)) == 2
        assert session.scalar(select(func.count()).select_from(WritingEvaluation)) == 2


def test_expired_different_fingerprint_conflicts_without_provider_call(factory) -> None:
    provider = FakeProvider([_payload()])
    with factory() as session:
        practice = _generated_practice(session)
        practice.lifecycle_state = "submission_in_progress"
        practice.claim_token = "stale-owner-token"
        practice.submission_fingerprint = submission_fingerprint(
            practice_id=practice.id, question=practice.question, essay="Owner essay."
        )
        now = session.scalar(select(func.current_timestamp()))
        assert now is not None
        practice.submission_claimed_at = now - timedelta(seconds=301)
        session.commit()

        result = asyncio.run(
            PracticeSubmissionService(session, WritingEvaluationService(provider)).submit(
                learner_id=1,
                practice_id=practice.id,
                submission=PracticeSubmission(essay="Different essay."),
            )
        )
        assert result.status == "conflict"
        assert not provider.requests


def test_reclaimed_old_token_cannot_finalize(factory) -> None:
    provider = FakeProvider([_payload()])
    with factory() as session:
        practice = _generated_practice(session)
        service = PracticeSubmissionService(session, WritingEvaluationService(provider))
        essay = "Recoverable essay."
        old_claim = service._claim(
            learner_id=1, practice_id=practice.id, essay=essay
        )
        assert isinstance(old_claim, tuple)
        old_token, writing_submission = old_claim
        current = session.get(WritingPractice, practice.id)
        assert current is not None
        now = session.scalar(select(func.current_timestamp()))
        assert now is not None
        current.submission_claimed_at = now - timedelta(seconds=301)
        session.commit()

        reclaimed = service._claim(
            learner_id=1, practice_id=practice.id, essay=essay
        )
        assert isinstance(reclaimed, tuple)
        new_token, _ = reclaimed
        assert new_token != old_token
        evaluation = asyncio.run(WritingEvaluationService(provider).evaluate(writing_submission))
        with pytest.raises(PracticeSubmissionPersistenceError):
            service._finalize(
                practice_id=practice.id,
                claim_token=old_token,
                submission=writing_submission,
                evaluation=evaluation,
            )
        finalized = service._finalize(
            practice_id=practice.id,
            claim_token=new_token,
            submission=writing_submission,
            evaluation=evaluation,
        )
        assert finalized.status == "submitted"
        assert len(provider.requests) == 1


def test_finalization_failure_resets_owned_claim_and_allows_retry(factory) -> None:
    """A recoverable PostgreSQL failure leaves no pair and releases our claim."""

    provider = FakeProvider([_payload(), _payload()])
    failed_once = False

    def fail_attempt_insert(_connection, _cursor, statement, _parameters, _context, _many) -> None:
        nonlocal failed_once
        if not failed_once and "INSERT INTO writing_attempts" in statement:
            failed_once = True
            raise OperationalError(statement, {}, Exception("forced finalization failure"))

    with factory() as session:
        sql_engine = session.get_bind()
        practice = _generated_practice(session)
        event.listen(sql_engine, "before_cursor_execute", fail_attempt_insert)
        try:
            service = PracticeSubmissionService(session, WritingEvaluationService(provider))
            with pytest.raises(PracticeSubmissionPersistenceError):
                asyncio.run(
                    service.submit(
                        learner_id=1,
                        practice_id=practice.id,
                        submission=PracticeSubmission(essay="Retryable finalization essay."),
                    )
                )
            session.rollback()
            reset = session.get(WritingPractice, practice.id)
            assert reset is not None
            assert reset.lifecycle_state == "generated"
            assert reset.submission_fingerprint is None
            assert reset.claim_token is None
            assert reset.attempt_id is None
            assert session.scalar(select(func.count()).select_from(WritingAttempt)) == 1
            assert session.scalar(select(func.count()).select_from(WritingEvaluation)) == 1

            retried = asyncio.run(
                service.submit(
                    learner_id=1,
                    practice_id=practice.id,
                    submission=PracticeSubmission(essay="Retryable finalization essay."),
                )
            )
            assert retried.status == "submitted"
            assert retried.attempt_id is not None
            assert retried.evaluation_id is not None
            assert len(provider.requests) == 2
            session.rollback()
            final = session.get(WritingPractice, practice.id)
            assert final is not None and final.attempt_id == retried.attempt_id
            assert session.scalar(select(func.count()).select_from(WritingAttempt)) == 2
            assert session.scalar(select(func.count()).select_from(WritingEvaluation)) == 2
        finally:
            event.remove(sql_engine, "before_cursor_execute", fail_attempt_insert)


def test_claim_cleanup_does_not_clear_different_owner_token(factory) -> None:
    with factory() as session:
        practice = _generated_practice(session)
        practice.lifecycle_state = "submission_in_progress"
        practice.submission_fingerprint = "f" * 64
        practice.claim_token = "new-owner-token"
        practice.submission_claimed_at = session.scalar(select(func.current_timestamp()))
        session.commit()

        PracticeSubmissionService(
            session, WritingEvaluationService(FakeProvider([]))
        )._reset_claim_if_owned(
            practice_id=practice.id,
            claim_token="old-owner-token",
        )
        session.rollback()
        unchanged = session.get(WritingPractice, practice.id)
        assert unchanged is not None
        assert unchanged.lifecycle_state == "submission_in_progress"
        assert unchanged.submission_fingerprint == "f" * 64
        assert unchanged.claim_token == "new-owner-token"


def test_agent_first_submission_freshness_fence_rejects_advanced_learner(factory) -> None:
    """Independent PostgreSQL sessions prove stale first submissions do no work."""

    provider = FakeProvider([_payload()])
    with factory() as agent_a:
        practice = _generated_practice(agent_a)
        recommendation_id = practice.recommendation_id
        recommendation = agent_a.get(PracticeRecommendation, recommendation_id)
        assert recommendation is not None
        expected_update_id = recommendation.learning_update_id
        practice_id = practice.id

    with factory() as agent_b:
        attempt, evaluation = _evaluation(identifier=901, attempt_id=902, band="6.0")
        agent_b.add_all([attempt, evaluation])
        agent_b.commit()
        apply_writing_evaluation(agent_b, learner_id=1, writing_evaluation_id=evaluation.id)

    with factory() as agent_a:
        with pytest.raises(Exception) as raised:
            asyncio.run(
                PracticeSubmissionService(agent_a, WritingEvaluationService(provider)).submit(
                    learner_id=1,
                    practice_id=practice_id,
                    submission=PracticeSubmission(essay="Stale first Agent essay."),
                    agent_expectation=AgentSubmissionExpectation(
                        expected_learning_update_id=expected_update_id,
                        expected_recommendation_id=recommendation_id,
                    ),
                )
            )
        assert raised.value.__class__.__name__ == "AgentStalePracticeError"
        stored = agent_a.get(WritingPractice, practice_id)
        assert stored is not None
        assert stored.lifecycle_state == "generated"
        assert stored.attempt_id is None
        assert agent_a.scalar(select(func.count()).select_from(WritingAttempt)) == 2
        assert agent_a.scalar(select(func.count()).select_from(WritingEvaluation)) == 2
    assert provider.requests == []


def test_agent_first_submission_fresh_current_fence_succeeds(factory) -> None:
    provider = FakeProvider([_payload()])
    with factory() as session:
        practice = _generated_practice(session)
        recommendation = session.get(PracticeRecommendation, practice.recommendation_id)
        assert recommendation is not None
        result = asyncio.run(
            PracticeSubmissionService(session, WritingEvaluationService(provider)).submit(
                learner_id=1,
                practice_id=practice.id,
                submission=PracticeSubmission(essay="Fresh first Agent essay."),
                agent_expectation=AgentSubmissionExpectation(
                    expected_learning_update_id=recommendation.learning_update_id,
                    expected_recommendation_id=recommendation.id,
                ),
            )
        )
    assert result.status == "submitted"
    assert len(provider.requests) == 1