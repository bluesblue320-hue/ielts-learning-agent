"""P10-09 isolated PostgreSQL proof for the canonical multi-episode case."""

import asyncio
import os
from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text

from app.agent.executor import AgentTurnExecutor
from app.agent.observation import observe_agent_state
from app.agent.tools import AgentTools
from app.db.session import create_session_factory
from app.eval.corpora import load_regression_corpus
from app.eval.lifecycle import LifecycleEvidence, OrderedLifecycleRecord, evaluate_lifecycle
from app.memory.episode_queries import list_learner_episodes
from app.models.learning import Learner, LearnerSkillState, LearningEvidence, LearningUpdate, PracticeRecommendation
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.agent import ContinueAgentTurn
from app.services.learning_application import apply_writing_evaluation
from app.services.practice_generation import PracticeGenerationService
from tests.fakes import FakePracticeGenerator
from tests.support.database import validate_test_database_url


pytestmark = pytest.mark.integration
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "eval"


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
        session.execute(text(
            "TRUNCATE writing_practices, practice_recommendations, learner_skill_states, "
            "learning_evidence, learning_updates, learners, writing_evaluations, "
            "writing_attempts RESTART IDENTITY CASCADE"
        ))
        session.commit()


def _add_episode(session, *, attempt_id: int, evaluation_id: int, created_at: datetime, band: str) -> None:
    session.add(WritingAttempt(
        id=attempt_id, question="Question", essay="Essay", word_count=1, created_at=created_at
    ))
    session.add(WritingEvaluation(
        id=evaluation_id,
        attempt_id=attempt_id,
        task_response_band=Decimal(band),
        coherence_and_cohesion_band=Decimal(band),
        lexical_resource_band=Decimal(band),
        grammatical_range_and_accuracy_band=Decimal(band),
        product_band=Decimal(band),
        criteria_feedback={}, strengths=[], weaknesses=[], error_tags=[], recommended_skills=[],
        feedback="Feedback.", provider="fake-provider", model="fake-model",
        prompt_version="fake-prompt", rubric_version="writing-task2-v1",
        scoring_policy_version="writing-task2-v1", thinking_mode="disabled", created_at=created_at,
    ))


def _read_counts(session) -> tuple[int, int, int]:
    return (
        session.scalar(select(func.count()).select_from(LearningUpdate)),
        session.scalar(select(func.count()).select_from(LearningEvidence)),
        session.scalar(select(func.count()).select_from(LearnerSkillState)),
    )


def test_multi_episode_authoritative_learning_loop_is_real_and_repeatable(factory) -> None:
    corpus = load_regression_corpus(FIXTURE_ROOT / "regression_corpus.json", fixture_directory=FIXTURE_ROOT)
    case = next(item for item in corpus.cases if item.case_id == "multi-episode-authoritative-learning-loop")
    assert case.multi_episode_lifecycle is not None

    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = datetime(2026, 2, 1, tzinfo=UTC)
    with factory() as session:
        session.add(Learner(id=1, writing_target_band=Decimal("7.0")))
        _add_episode(session, attempt_id=100, evaluation_id=200, created_at=older, band="6.0")
        _add_episode(session, attempt_id=101, evaluation_id=201, created_at=newer, band="7.0")
        session.commit()

        # Episode 2 is accepted first; the late older episode must rebuild State canonically.
        accepted_newer = apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=201)
        accepted_older = apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)
        replay = apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)
        assert replay.reused is True
        assert replay.learning_update_id == accepted_older.learning_update_id

        state = session.get(LearnerSkillState, (1, "task_response"))
        assert state is not None and state.estimated_band == Decimal("6.50")
        assert state.last_evidence_id is not None
        last_evidence = session.get(LearningEvidence, state.last_evidence_id)
        assert last_evidence is not None and last_evidence.source_attempt_id == 101

        episodes = list_learner_episodes(session, learner_id=1)
        updates = session.scalars(select(LearningUpdate).where(LearningUpdate.learner_id == 1)).all()
        current_update = max(updates, key=lambda row: row.id)
        current_recommendation = session.scalar(select(PracticeRecommendation).where(
            PracticeRecommendation.learning_update_id == current_update.id
        ))
        assert current_recommendation is not None and current_recommendation.learner_id == 1
        generated = asyncio.run(PracticeGenerationService(session, FakePracticeGenerator()).generate_or_resolve_current(
            learner_id=1,
            recommendation_id=current_recommendation.id,
            expected_learning_update_id=current_update.id,
        ))
        assert generated.status == "generated" and generated.practice is not None
        observed = observe_agent_state(session, learner_id=1)
        response = asyncio.run(AgentTurnExecutor(
            tools=AgentTools(session=session), observe=lambda learner_id: observe_agent_state(session, learner_id=learner_id)
        ).execute(learner_id=1, turn=ContinueAgentTurn(turn_type="continue")))
        assert response.current_practice is not None and response.current_practice.id == generated.practice.id
        assert observed.latest_learning_update_id == current_update.id

        before = _read_counts(session)
        repeated_episodes = list_learner_episodes(session, learner_id=1)
        after = _read_counts(session)
        attempts = session.scalars(select(WritingAttempt).where(WritingAttempt.id.in_((100, 101)))).all()
        evidence = LifecycleEvidence(
            learner_id=1,
            writing_evaluation_ids=tuple(update.writing_evaluation_id for update in updates),
            learning_updates=tuple(OrderedLifecycleRecord(id=update.id, created_at=update.created_at) for update in updates),
            learning_update_evaluation_ids=tuple(update.writing_evaluation_id for update in updates),
            attempts_in_state_order=tuple(
                OrderedLifecycleRecord(id=attempt.id, created_at=attempt.created_at)
                for attempt in sorted(attempts, key=lambda item: (item.created_at, item.id))
            ),
            state_last_attempt_id=last_evidence.source_attempt_id,
            memory_update_ids=tuple(episode.episode_id for episode in episodes),
            current_learning_update_id=observed.latest_learning_update_id,
            recommendation_id=current_recommendation.id,
            recommendation_learner_id=current_recommendation.learner_id,
            recommendation_learning_update_id=current_recommendation.learning_update_id,
            practice_id=generated.practice.id,
            practice_learner_id=generated.practice.learner_id,
            practice_recommendation_id=generated.practice.recommendation_id,
            read_counts_before=before,
            read_counts_after=after,
        )
        assert tuple(episode.episode_id for episode in repeated_episodes) == evidence.memory_update_ids
        assert evaluate_lifecycle(evidence).status.value == "pass"
        assert session.scalar(select(func.count()).select_from(WritingPractice)) == 1
        assert len(episodes) == 2
        assert accepted_newer.learning_update_id in evidence.memory_update_ids
