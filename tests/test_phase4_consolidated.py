"""P4-14 end-to-end acceptance evidence for the complete adaptive loop."""

import asyncio

import pytest
from sqlalchemy import func, select

from app.models.learning import LearningEvidence, LearningUpdate, PracticeRecommendation
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.services.practice_completion import PracticeCompletionService
from app.services.practice_generation import PracticeGenerationService
from app.services.practice_submission import PracticeSubmissionService
from app.services.writing_evaluation import WritingEvaluationService
from tests.fakes import FakePracticeGenerator, FakeProvider
from tests.test_practice_generation import _recommendation, factory, truncate
from tests.test_practice_submission import _payload


pytestmark = [pytest.mark.integration, pytest.mark.provider]


def _high_payload() -> dict[str, object]:
    payload = _payload()
    for criterion in payload["criteria"].values():
        criterion["band"] = {"value": "9.0"}
    return payload


def test_full_loop_persists_one_trace_and_can_replan_to_no_practice(factory) -> None:
    generator = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session)
        generated = asyncio.run(
            PracticeGenerationService(session, generator).generate_or_resolve(
                learner_id=1, recommendation_id=recommendation.id
            )
        )
        assert generated.practice is not None
        submitted = asyncio.run(
            PracticeSubmissionService(
                session, WritingEvaluationService(FakeProvider([_high_payload()]))
            ).submit(
                learner_id=1,
                practice_id=generated.practice.id,
                submission={"essay": "A valid response to the persisted practice."},
            )
        )
        completed = PracticeCompletionService(session).complete(
            learner_id=1, practice_id=generated.practice.id
        )

        assert submitted.status == "submitted"
        assert completed.next_recommendation.decision_type.value == "no_practice"
        assert len(generator.requests) == 1
        assert session.scalar(select(func.count()).select_from(WritingPractice)) == 1
        assert session.scalar(select(func.count()).select_from(WritingAttempt)) == 2
        assert session.scalar(select(func.count()).select_from(WritingEvaluation)) == 2
        assert session.scalar(select(func.count()).select_from(LearningUpdate)) == 2
        assert session.scalar(select(func.count()).select_from(LearningEvidence)) == 8
        assert session.scalar(select(func.count()).select_from(PracticeRecommendation)) == 2
