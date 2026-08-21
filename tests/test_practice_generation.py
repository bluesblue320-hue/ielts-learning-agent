"""P4-09 real-PostgreSQL coverage for decision-gated practice generation."""

import asyncio
import os
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import create_session_factory
from app.models.learning import Learner, LearningUpdate, PracticeRecommendation
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.services.learning_application import apply_writing_evaluation
from app.services.practice_generation import (
    GeneratedPracticeAuthorityError,
    PracticeGenerationService,
    RecommendationOwnershipError,
)
from app.schemas.practice import GeneratedWritingPractice
from tests.fakes import FakePracticeGenerator
from tests.support.database import validate_test_database_url


pytestmark = pytest.mark.integration
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _config(url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


@pytest.fixture(scope="module")
def factory() -> Generator[object, None, None]:
    url = os.getenv("IELTS_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("IELTS_TEST_DATABASE_URL is required for PostgreSQL integration")
    validate_test_database_url(url, os.getenv("IELTS_DATABASE_URL"))
    engine = create_engine(url)
    command.upgrade(_config(url), "head")
    yield create_session_factory(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def truncate(factory) -> None:
    with factory() as session:
        session.execute(
            text(
                "TRUNCATE writing_practices, practice_recommendations, "
                "learner_skill_states, learning_evidence, learning_updates, "
                "learners, writing_evaluations, writing_attempts RESTART IDENTITY CASCADE"
            )
        )
        session.commit()


def _evaluation(*, identifier: int, attempt_id: int, band: str) -> tuple[WritingAttempt, WritingEvaluation]:
    attempt = WritingAttempt(
        id=attempt_id,
        question="Question",
        essay="Essay",
        word_count=1,
        created_at=NOW,
    )
    evaluation = WritingEvaluation(
        id=identifier,
        attempt_id=attempt_id,
        task_response_band=Decimal(band),
        coherence_and_cohesion_band=Decimal(band),
        lexical_resource_band=Decimal(band),
        grammatical_range_and_accuracy_band=Decimal(band),
        product_band=Decimal(band),
        criteria_feedback={},
        strengths=[],
        weaknesses=[],
        error_tags=[],
        recommended_skills=[],
        feedback="Feedback.",
        provider="fake-provider",
        model="fake-model",
        prompt_version="fake-prompt",
        rubric_version="fake-rubric",
        scoring_policy_version="fake-policy",
        thinking_mode="disabled",
        created_at=NOW,
    )
    attempt.evaluation = evaluation
    return attempt, evaluation


def _recommendation(
    session: Session,
    *,
    learner_id: int = 1,
    evaluation_id: int = 100,
    attempt_id: int = 10,
    band: str = "6.0",
) -> PracticeRecommendation:
    session.add(Learner(id=learner_id, writing_target_band=Decimal("7.0")))
    attempt, evaluation = _evaluation(
        identifier=evaluation_id,
        attempt_id=attempt_id,
        band=band,
    )
    session.add_all([attempt, evaluation])
    session.commit()
    result = apply_writing_evaluation(
        session,
        learner_id=learner_id,
        writing_evaluation_id=evaluation_id,
    )
    row = session.scalar(
        select(PracticeRecommendation).where(
            PracticeRecommendation.learning_update_id == result.learning_update_id
        )
    )
    assert row is not None
    return row


def test_first_generation_persists_authoritative_content_and_provenance(factory) -> None:
    fake = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session)
        outcome = asyncio.run(
            PracticeGenerationService(session, fake).generate_or_resolve(
                learner_id=1, recommendation_id=recommendation.id
            )
        )
        assert outcome.decision == "practice"
        assert outcome.practice is not None
        assert outcome.practice.target_skill == recommendation.target_skill
        assert outcome.practice.provider == "fake-practice-provider"
        assert outcome.practice.lifecycle_state.value == "generated"
        assert len(fake.requests) == 1
        assert session.scalar(select(func.count()).select_from(WritingPractice)) == 1


def test_retry_returns_existing_practice_without_a_second_generator_call(factory) -> None:
    fake = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session)
        service = PracticeGenerationService(session, fake)
        first = asyncio.run(service.generate_or_resolve(learner_id=1, recommendation_id=recommendation.id))
        second = asyncio.run(service.generate_or_resolve(learner_id=1, recommendation_id=recommendation.id))
        assert first.practice is not None and second.practice is not None
        assert second.practice.id == first.practice.id
        assert len(fake.requests) == 1


def test_no_practice_decision_has_zero_generator_calls_and_zero_practice_rows(factory) -> None:
    fake = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session, band="7.0")
        assert recommendation.decision_type == "no_practice"
        outcome = asyncio.run(
            PracticeGenerationService(session, fake).generate_or_resolve(
                learner_id=1, recommendation_id=recommendation.id
            )
        )
        assert outcome.decision == "no_practice"
        assert outcome.practice is None
        assert len(fake.requests) == 0
        assert session.scalar(select(func.count()).select_from(WritingPractice)) == 0


def test_cold_start_no_practice_has_zero_generator_calls_and_zero_rows(factory) -> None:
    fake = FakePracticeGenerator()
    with factory() as session:
        session.add(Learner(id=1, writing_target_band=Decimal("7.0")))
        attempt, evaluation = _evaluation(identifier=100, attempt_id=10, band="6.0")
        session.add_all([attempt, evaluation])
        session.flush()
        update = LearningUpdate(
            learner_id=1,
            writing_evaluation_id=100,
            skill_taxonomy_version="writing-core-v1",
            state_policy_version="writing-state-ewma-v1",
            planner_version="writing-practice-gap-v1",
        )
        session.add(update)
        session.flush()
        cold_start = PracticeRecommendation(
            learning_update_id=update.id,
            learner_id=1,
            decision_type="no_practice",
            target_skill=None,
            learner_target_band=Decimal("7.0"),
            current_estimate=None,
            reason_codes=["cold_start"],
            planner_version="writing-practice-gap-v1",
            state_snapshot={
                "task_response": {},
                "coherence_and_cohesion": {},
                "lexical_resource": {},
                "grammatical_range_and_accuracy": {},
            },
        )
        session.add(cold_start)
        session.commit()

        outcome = asyncio.run(
            PracticeGenerationService(session, fake).generate_or_resolve(
                learner_id=1, recommendation_id=cold_start.id
            )
        )
        assert outcome.decision == "no_practice"
        assert outcome.no_practice_reasons == ["cold_start"]
        assert not fake.requests
        assert session.scalar(select(func.count()).select_from(WritingPractice)) == 0


def test_cross_learner_request_is_rejected_before_generator_call(factory) -> None:
    fake = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session)
        with pytest.raises(RecommendationOwnershipError):
            asyncio.run(
                PracticeGenerationService(session, fake).generate_or_resolve(
                    learner_id=2, recommendation_id=recommendation.id
                )
            )
        assert not fake.requests


def test_provider_failure_creates_no_practice_row(factory) -> None:
    from app.llm import ProviderError, ProviderErrorCategory, ProviderErrorContext

    failure = ProviderError(
        ProviderErrorCategory.TRANSIENT,
        "Safe failure.",
        context=ProviderErrorContext(provider="fake-practice-provider", operation="generate_practice"),
    )
    fake = FakePracticeGenerator([failure])
    with factory() as session:
        recommendation = _recommendation(session)
        with pytest.raises(ProviderError):
            asyncio.run(
                PracticeGenerationService(session, fake).generate_or_resolve(
                    learner_id=1, recommendation_id=recommendation.id
                )
            )
        assert session.scalar(select(func.count()).select_from(WritingPractice)) == 0


def test_generator_authority_mismatch_creates_no_practice_row(factory) -> None:
    mismatched = GeneratedWritingPractice(
        practice_type="task2_targeted_focus",
        target_skill="lexical_resource",
        question="Question?",
        focus_objective="Objective.",
        instructions=["Instruction."],
        checkpoints=["Checkpoint."],
        generator_policy_version="writing-practice-generation-v1",
        provider="fake",
        model="fake",
        prompt_version="practice-generation-v1",
        thinking_mode="disabled",
    )
    with factory() as session:
        recommendation = _recommendation(session)
        with pytest.raises(GeneratedPracticeAuthorityError):
            asyncio.run(
                PracticeGenerationService(
                    session, FakePracticeGenerator([mismatched])
                ).generate_or_resolve(learner_id=1, recommendation_id=recommendation.id)
            )
        assert session.scalar(select(func.count()).select_from(WritingPractice)) == 0


def test_database_rejects_cross_learner_recommendation_ownership(factory) -> None:
    with factory() as session:
        recommendation = _recommendation(session)
        session.add(Learner(id=2, writing_target_band=Decimal("7.0")))
        session.commit()
        practice = WritingPractice(
            learner_id=2,
            recommendation_id=recommendation.id,
            target_skill="task_response",
            practice_type="task2_targeted_focus",
            question="Question?",
            focus_objective="Objective.",
            instructions=["Instruction."],
            checkpoints=["Checkpoint."],
            generator_policy_version="writing-practice-generation-v1",
            provider="fake",
            model="fake",
            prompt_version="practice-generation-v1",
            thinking_mode="disabled",
            lifecycle_state="generated",
        )
        session.add(practice)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_concurrent_first_generation_returns_one_durable_winner(factory) -> None:
    with factory() as session:
        recommendation = _recommendation(session)
        recommendation_id = recommendation.id

    barrier = threading.Barrier(2)

    def generate() -> int:
        fake = FakePracticeGenerator()
        with factory() as session:
            barrier.wait(timeout=10)
            outcome = asyncio.run(
                PracticeGenerationService(session, fake).generate_or_resolve(
                    learner_id=1, recommendation_id=recommendation_id
                )
            )
            assert outcome.practice is not None
            return outcome.practice.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: generate(), range(2)))

    assert ids[0] == ids[1]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(WritingPractice)) == 1


def test_agent_generation_provider_accounting_four_branches(factory, monkeypatch) -> None:
    """The Agent charges provider budget only when its generator actually ran."""

    # A: stale preflight makes no provider call.
    stale_generator = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session, learner_id=1, evaluation_id=100, attempt_id=10)
        stale = asyncio.run(
            PracticeGenerationService(session, stale_generator).generate_or_resolve_current(
                learner_id=1,
                recommendation_id=recommendation.id,
                expected_learning_update_id=recommendation.learning_update_id + 1,
            )
        )
    assert stale.status == "stale_discarded"
    assert stale.provider_invoked is False
    assert stale_generator.requests == []

    # B: an existing durable practice resolves without the generator.
    resolved_generator = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session, learner_id=2, evaluation_id=200, attempt_id=20)
        first = asyncio.run(
            PracticeGenerationService(session, resolved_generator).generate_or_resolve_current(
                    learner_id=2,
                recommendation_id=recommendation.id,
                expected_learning_update_id=recommendation.learning_update_id,
            )
        )
        assert first.status == "generated"
        resolved = asyncio.run(
            PracticeGenerationService(session, resolved_generator).generate_or_resolve_current(
                    learner_id=2,
                recommendation_id=recommendation.id,
                expected_learning_update_id=recommendation.learning_update_id,
            )
        )
    assert resolved.status == "resolved"
    assert resolved.provider_invoked is False
    assert len(resolved_generator.requests) == 1

    # C: provider runs, then the pre-persist fence discards the stale candidate.
    stale_after_provider = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session, learner_id=3, evaluation_id=300, attempt_id=30)
        service = PracticeGenerationService(session, stale_after_provider)
        monkeypatch.setattr(service, "_persist_if_agent_current", lambda **_kwargs: None)
        discarded = asyncio.run(
            service.generate_or_resolve_current(
                learner_id=3,
                recommendation_id=recommendation.id,
                expected_learning_update_id=recommendation.learning_update_id,
            )
        )
        assert session.scalar(select(func.count()).select_from(WritingPractice).where(WritingPractice.recommendation_id == recommendation.id)) == 0
    assert discarded.status == "stale_discarded"
    assert discarded.provider_invoked is True
    assert len(stale_after_provider.requests) == 1

    # D: provider runs and a current fenced persistence succeeds.
    fresh_generator = FakePracticeGenerator()
    with factory() as session:
        recommendation = _recommendation(session, learner_id=4, evaluation_id=400, attempt_id=40)
        fresh = asyncio.run(
            PracticeGenerationService(session, fresh_generator).generate_or_resolve_current(
                learner_id=4,
                recommendation_id=recommendation.id,
                expected_learning_update_id=recommendation.learning_update_id,
            )
        )
    assert fresh.status == "generated"
    assert fresh.provider_invoked is True
    assert len(fresh_generator.requests) == 1
