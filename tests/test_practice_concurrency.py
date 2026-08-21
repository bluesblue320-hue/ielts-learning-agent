"""P4-13 real-PostgreSQL concurrency proof for practice submission claims."""

import asyncio
import threading

import pytest
from sqlalchemy import func, select

from app.llm import ThinkingMode
from app.llm.provider import WritingProviderRequest
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.writing import ProviderEvaluationPayload
from app.services.practice_generation import PracticeGenerationService
from app.services.practice_submission import PracticeSubmissionService
from app.services.writing_evaluation import WritingEvaluationService
from tests.fakes import FakePracticeGenerator
from tests.test_practice_generation import _recommendation, factory, truncate
from tests.test_practice_submission import _payload


pytestmark = [pytest.mark.integration, pytest.mark.provider]


class BlockingProvider:
    """Blocks exactly one evaluation after the durable claim is committed."""

    provider_name = "blocking-provider"
    model_name = "blocking-model"
    thinking_mode = ThinkingMode.DISABLED

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.requests: list[WritingProviderRequest] = []

    async def evaluate_writing(
        self, request: WritingProviderRequest
    ) -> ProviderEvaluationPayload:
        self.requests.append(request)
        self.started.set()
        assert await asyncio.to_thread(self.release.wait, 10)
        return ProviderEvaluationPayload.model_validate(_payload())


def _practice_id(factory) -> int:
    with factory() as session:
        recommendation = _recommendation(session)
        outcome = asyncio.run(
            PracticeGenerationService(session, FakePracticeGenerator()).generate_or_resolve(
                learner_id=1, recommendation_id=recommendation.id
            )
        )
        assert outcome.practice is not None
        return outcome.practice.id


def test_concurrent_submission_has_one_claim_one_provider_and_one_pair(factory) -> None:
    practice_id = _practice_id(factory)
    provider = BlockingProvider()
    first_result: list[object] = []
    first_errors: list[BaseException] = []

    def first_submit() -> None:
        try:
            with factory() as session:
                first_result.append(
                    asyncio.run(
                        PracticeSubmissionService(
                            session, WritingEvaluationService(provider)
                        ).submit(
                            learner_id=1,
                            practice_id=practice_id,
                            submission={"essay": "First concurrent essay."},
                        )
                    )
                )
        except BaseException as error:  # pragma: no cover - surfaced below
            first_errors.append(error)

    owner = threading.Thread(target=first_submit)
    owner.start()
    assert provider.started.wait(timeout=10)

    with factory() as session:
        follower = asyncio.run(
            PracticeSubmissionService(session, WritingEvaluationService(provider)).submit(
                learner_id=1,
                practice_id=practice_id,
                submission={"essay": "First concurrent essay."},
            )
        )
    assert follower.status == "in_progress"
    assert len(provider.requests) == 1

    provider.release.set()
    owner.join(timeout=15)
    assert not owner.is_alive()
    assert not first_errors
    assert first_result[0].status == "submitted"

    with factory() as session:
        practice = session.get(WritingPractice, practice_id)
        assert practice is not None and practice.lifecycle_state == "submitted"
        assert practice.attempt_id is not None
        assert session.scalar(select(func.count()).select_from(WritingAttempt)) == 2
        assert session.scalar(select(func.count()).select_from(WritingEvaluation)) == 2
