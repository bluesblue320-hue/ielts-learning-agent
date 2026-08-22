"""Real-PostgreSQL chronology regression for grounded Writing guidance."""

from __future__ import annotations

import os
import threading
from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, select, text

from app.db.session import create_session_factory
from app.models.learning import Learner, LearnerSkillState, LearningUpdate, PracticeRecommendation
from app.models.writing import WritingAttempt, WritingEvaluation
from app.services.learning_application import apply_writing_evaluation
from app.services.writing_guidance import WritingGuidanceService
from tests.support.database import validate_test_database_url

pytestmark = pytest.mark.integration

TA = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
TB = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
_SKILLS = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="module")
def database() -> Generator[tuple[Engine, object], None, None]:
    url = os.getenv("IELTS_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("IELTS_TEST_DATABASE_URL is required for PostgreSQL integration")
    validate_test_database_url(url, os.getenv("IELTS_DATABASE_URL"))
    engine = create_engine(url)
    command.upgrade(_alembic_config(url), "head")
    factory = create_session_factory(engine)
    yield engine, factory
    engine.dispose()


@pytest.fixture(autouse=True)
def _truncate(database: tuple[Engine, object]) -> Generator[None, None, None]:
    engine, _factory = database
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE writing_practices, practice_recommendations, "
                "learner_skill_states, learning_evidence, learning_updates, "
                "learners, writing_evaluations, writing_attempts "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


def _add_evaluation(
    session: object,
    *,
    evaluation_id: int,
    attempt_id: int,
    created_at: datetime,
    band: str,
) -> None:
    session.add(
        WritingAttempt(
            id=attempt_id,
            question="Q",
            essay="E",
            word_count=1,
            created_at=created_at,
        )
    )
    session.add(
        WritingEvaluation(
            id=evaluation_id,
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
            feedback="f",
            provider="deepseek",
            model="deepseek-chat",
            prompt_version="writing-v2",
            rubric_version="writing-task2-v1",
            scoring_policy_version="writing-scoring-v1",
            thinking_mode="disabled",
            created_at=created_at,
        )
    )


def test_guidance_cannot_mix_update_n_snapshot_with_update_n_plus_one_recommendation(
    database: tuple[Engine, object],
) -> None:
    engine, factory = database
    with factory() as session:
        session.add(Learner(id=1, writing_target_band=Decimal("7.0")))
        _add_evaluation(session, evaluation_id=200, attempt_id=100, created_at=TA, band="5.0")
        _add_evaluation(session, evaluation_id=201, attempt_id=101, created_at=TB, band="9.0")
        session.commit()
        first = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )

    latest_update_selected = threading.Event()
    allow_guidance_to_continue = threading.Event()
    guidance_thread_id: dict[str, int] = {}
    outcome: dict[str, object] = {}

    def pause_after_latest_update_query(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if (
            threading.get_ident() == guidance_thread_id.get("value")
            and "FROM learning_updates" in statement
            and "ORDER BY learning_updates.id DESC" in statement
        ):
            latest_update_selected.set()
            if not allow_guidance_to_continue.wait(timeout=15):
                raise AssertionError("guidance synchronization was not released")

    def read_guidance() -> None:
        guidance_thread_id["value"] = threading.get_ident()
        try:
            with factory() as session:
                outcome["response"] = WritingGuidanceService(session).get(learner_id=1)
        except BaseException as error:  # pragma: no cover - surfaced in main thread
            outcome["error"] = error

    event.listen(engine, "after_cursor_execute", pause_after_latest_update_query)
    worker = threading.Thread(target=read_guidance, name="phase9-guidance-reader")
    try:
        worker.start()
        assert latest_update_selected.wait(timeout=15), "guidance did not select update N"

        with factory() as session:
            second = apply_writing_evaluation(
                session, learner_id=1, writing_evaluation_id=201
            )

        allow_guidance_to_continue.set()
        worker.join(timeout=15)
        assert not worker.is_alive(), "guidance reader did not finish"
    finally:
        allow_guidance_to_continue.set()
        worker.join(timeout=15)
        event.remove(engine, "after_cursor_execute", pause_after_latest_update_query)

    if "error" in outcome:
        raise outcome["error"]  # type: ignore[misc]
    response = outcome["response"]

    assert first.learning_update_id < second.learning_update_id
    assert response.current_recommendation is not None
    assert response.current_recommendation.id == first.recommendation_id
    assert set(response.learner_state.current_estimates.values()) == {Decimal("5.00")}

    with factory() as session:
        latest = session.scalar(select(LearningUpdate).order_by(LearningUpdate.id.desc()))
        latest_recommendation = session.scalar(
            select(PracticeRecommendation).where(
                PracticeRecommendation.learning_update_id == latest.id
            )
        )
        live_states = session.scalars(
            select(LearnerSkillState).where(LearnerSkillState.learner_id == 1)
        ).all()

    assert latest.id == second.learning_update_id
    assert latest_recommendation.id == second.recommendation_id
    assert latest_recommendation.id != response.current_recommendation.id
    assert {state.skill for state in live_states} == set(_SKILLS)
    assert {state.estimated_band for state in live_states} == {Decimal("7.00")}
