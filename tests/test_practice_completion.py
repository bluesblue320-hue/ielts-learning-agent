"""P4-11 isolated PostgreSQL closed-loop completion tests."""

import asyncio

import pytest
from sqlalchemy import func, select

from app.models.learning import LearningEvidence, LearningUpdate, PracticeRecommendation
from app.services.practice_completion import PracticeCompletionService
from app.services.practice_generation import PracticeGenerationService
from app.services.practice_submission import PracticeSubmissionService
from app.services.writing_evaluation import WritingEvaluationService
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_practice_generation import _recommendation, factory, truncate
from tests.test_practice_submission import _payload


pytestmark = [pytest.mark.integration, pytest.mark.provider]


def _submitted_practice(session):
    recommendation = _recommendation(session)
    generated = asyncio.run(
        PracticeGenerationService(session, FakePracticeGenerator()).generate_or_resolve(
            learner_id=1, recommendation_id=recommendation.id
        )
    )
    assert generated.practice is not None
    submitted = asyncio.run(
        PracticeSubmissionService(
            session,
            WritingEvaluationService(FakeProvider([_payload()])),
        ).submit(
            learner_id=1,
            practice_id=generated.practice.id,
            submission={"essay": "A learner response for the generated question."},
        )
    )
    return generated.practice.id, submitted


def test_completion_applies_submitted_evaluation_and_returns_next_recommendation(factory) -> None:
    with factory() as session:
        practice_id, submitted = _submitted_practice(session)
        completed = PracticeCompletionService(session).complete(
            learner_id=1,
            practice_id=practice_id,
        )
        assert completed.practice_id == practice_id
        assert completed.attempt_id == submitted.attempt_id
        assert completed.evaluation_id == submitted.evaluation_id
        assert completed.next_recommendation.decision_type.value in {"practice", "no_practice"}
        assert session.scalar(select(func.count()).select_from(LearningUpdate)) == 2
        assert session.scalar(select(func.count()).select_from(LearningEvidence)) == 8
        assert session.scalar(select(func.count()).select_from(PracticeRecommendation)) == 2


def test_completion_retry_reuses_phase3_apply_without_duplicate_effects(factory) -> None:
    with factory() as session:
        practice_id, _ = _submitted_practice(session)
        service = PracticeCompletionService(session)
        first = service.complete(learner_id=1, practice_id=practice_id)
        second = service.complete(learner_id=1, practice_id=practice_id)
        assert second.learning_update_id == first.learning_update_id
        assert session.scalar(select(func.count()).select_from(LearningUpdate)) == 2
        assert session.scalar(select(func.count()).select_from(LearningEvidence)) == 8
        assert session.scalar(select(func.count()).select_from(PracticeRecommendation)) == 2
