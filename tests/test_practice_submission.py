"""P4-10 real-PostgreSQL submission-claim and atomic-finalization tests."""

import asyncio

import pytest
from sqlalchemy import func, select

from app.llm import ProviderError, ProviderErrorCategory, ProviderErrorContext
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.practice import PracticeSubmission
from app.services.practice_generation import PracticeGenerationService
from app.services.practice_submission import PracticeSubmissionService
from app.services.writing_evaluation import WritingEvaluationService
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_practice_generation import _recommendation, factory, truncate


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
        practice.submission_fingerprint = "f" * 64
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
