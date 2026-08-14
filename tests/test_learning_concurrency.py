"""P3-12 concurrency / idempotency hardening against real PostgreSQL.

These tests prove that concurrent applications cannot double-apply, corrupt
state, or let transaction completion order override canonical evidence order.
"""

import os
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, func, select, text

from app.db.session import create_session_factory
from app.models.learning import (
    Learner,
    LearnerSkillState,
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
)
from app.models.writing import WritingAttempt, WritingEvaluation
from app.services.learning_application import apply_writing_evaluation
from tests.support.database import validate_test_database_url

TA = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)  # older
TB = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)  # newer

BANDS_A = {
    "task_response": "6.0",
    "coherence_and_cohesion": "6.5",
    "lexical_resource": "6.5",
    "grammatical_range_and_accuracy": "6.5",
}
BANDS_B = {
    "task_response": "7.0",
    "coherence_and_cohesion": "7.0",
    "lexical_resource": "7.0",
    "grammatical_range_and_accuracy": "7.0",
}


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="module")
def factory() -> Generator[object, None, None]:
    url = os.getenv("IELTS_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("IELTS_TEST_DATABASE_URL is required for PostgreSQL integration")
    validate_test_database_url(url, os.getenv("IELTS_DATABASE_URL"))
    engine = create_engine(url)
    command.upgrade(_alembic_config(url), "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE practice_recommendations, learner_skill_states, "
                "learning_evidence, learning_updates, learners, "
                "writing_evaluations, writing_attempts RESTART IDENTITY CASCADE"
            )
        )
    session_factory = create_session_factory(engine)
    yield session_factory
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE practice_recommendations, learner_skill_states, "
                "learning_evidence, learning_updates, learners, "
                "writing_evaluations, writing_attempts RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()


@pytest.fixture(autouse=True)
def _truncate_before(factory) -> None:
    """Start every test from an empty Phase 3 + Phase 2 fixture slate."""
    with factory() as session:
        session.execute(
            text(
                "TRUNCATE practice_recommendations, learner_skill_states, "
                "learning_evidence, learning_updates, learners, "
                "writing_evaluations, writing_attempts RESTART IDENTITY CASCADE"
            )
        )
        session.commit()
    yield


def _add_learner(session, learner_id: int = 1) -> None:
    session.add(Learner(id=learner_id, writing_target_band=Decimal("7.0")))


def _add_evaluation(
    session,
    *,
    evaluation_id: int,
    attempt_id: int,
    created_at: datetime,
    bands: dict[str, str],
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
            task_response_band=Decimal(bands["task_response"]),
            coherence_and_cohesion_band=Decimal(bands["coherence_and_cohesion"]),
            lexical_resource_band=Decimal(bands["lexical_resource"]),
            grammatical_range_and_accuracy_band=Decimal(
                bands["grammatical_range_and_accuracy"]
            ),
            product_band=Decimal("6.5"),
            criteria_feedback={},
            strengths=[],
            weaknesses=[],
            error_tags=[],
            recommended_skills=[],
            feedback="f",
            provider="deepseek",
            model="m",
            prompt_version="pv",
            rubric_version="rv",
            scoring_policy_version="sv",
            thinking_mode="disabled",
            created_at=created_at,
        )
    )


def _counts(session) -> dict[str, int]:
    return {
        "updates": session.scalar(select(func.count()).select_from(LearningUpdate)),
        "evidence": session.scalar(select(func.count()).select_from(LearningEvidence)),
        "states": session.scalar(select(func.count()).select_from(LearnerSkillState)),
        "recommendations": session.scalar(
            select(func.count()).select_from(PracticeRecommendation)
        ),
    }


def _tr_state(session, learner_id: int = 1) -> LearnerSkillState:
    return session.get(LearnerSkillState, (learner_id, "task_response"))


def _run_apply(factory, learner_id: int, evaluation_id: int, barrier):
    barrier.wait()
    with factory() as session:
        try:
            result = apply_writing_evaluation(
                session, learner_id=learner_id, writing_evaluation_id=evaluation_id
            )
            return result.reused, result.learning_update_id
        except Exception as error:  # pragma: no cover - failure must fail the test
            return ("error", type(error).__name__)


def _run_concurrently(factory, work: list[tuple[int, int]]) -> list:
    barrier = threading.Barrier(len(work))
    with ThreadPoolExecutor(max_workers=len(work)) as pool:
        futures = [
            pool.submit(_run_apply, factory, learner_id, evaluation_id, barrier)
            for learner_id, evaluation_id in work
        ]
        return [future.result() for future in futures]


# ---------------------------------------------------------------------------
# Same learner + same evaluation
# ---------------------------------------------------------------------------


def test_concurrent_same_evaluation_applies_once(factory) -> None:
    with factory() as session:
        _add_learner(session)
        _add_evaluation(
            session, evaluation_id=200, attempt_id=100, created_at=TA, bands=BANDS_A
        )
        session.commit()

    results = _run_concurrently(factory, [(1, 200), (1, 200)])

    # Exactly one creation and one idempotent reuse; no duplicate effects.
    assert sorted(result[0] for result in results) == [False, True]
    assert results[0][1] == results[1][1]

    with factory() as session:
        assert _counts(session) == {
            "updates": 1,
            "evidence": 4,
            "states": 4,
            "recommendations": 1,
        }
        assert _tr_state(session).evidence_count == 1
        assert _tr_state(session).revision == 1
        assert _tr_state(session).estimated_band == Decimal("6.00")


def test_repeated_concurrent_same_evaluation_stays_stable(factory) -> None:
    with factory() as session:
        _add_learner(session)
        _add_evaluation(
            session, evaluation_id=200, attempt_id=100, created_at=TA, bands=BANDS_A
        )
        session.commit()

    for round_index in range(4):
        results = _run_concurrently(factory, [(1, 200), (1, 200), (1, 200)])
        expected = [False, True, True] if round_index == 0 else [True, True, True]
        assert sorted(result[0] for result in results) == expected

    with factory() as session:
        assert _counts(session) == {
            "updates": 1,
            "evidence": 4,
            "states": 4,
            "recommendations": 1,
        }


# ---------------------------------------------------------------------------
# Same learner + different evaluations: canonical order must win
# ---------------------------------------------------------------------------


def test_concurrent_different_evaluations_match_canonical_replay(factory) -> None:
    with factory() as session:
        _add_learner(session)
        _add_evaluation(
            session, evaluation_id=200, attempt_id=100, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=201, attempt_id=101, created_at=TB, bands=BANDS_B
        )
        session.commit()

    # Concurrent applications of the two evaluations; commit order is unknown.
    results = _run_concurrently(factory, [(1, 200), (1, 201)])
    assert all(result[0] is False for result in results)

    with factory() as session:
        counts = _counts(session)
        assert counts == {"updates": 2, "evidence": 8, "states": 4, "recommendations": 2}

        # Canonical replay(A, B): TR = (6.0, 7.0) -> EWMA 6.50.
        state = _tr_state(session)
        assert state.estimated_band == Decimal("6.50")
        assert state.evidence_count == 2
        assert state.revision == 2
        # Canonical last evidence is the newer attempt (101), regardless of
        # which transaction committed last.
        last = session.get(LearningEvidence, state.last_evidence_id)
        assert last.source_attempt_id == 101

        # Every update owns exactly one recommendation.
        update_ids = set(
            session.scalars(select(LearningUpdate.id)).all()
        )
        recommendation_ids = set(
            session.scalars(
                select(PracticeRecommendation.learning_update_id)
            ).all()
        )
        assert update_ids == recommendation_ids
        assert len(update_ids) == 2


def test_concurrent_equals_sequential_and_late_arrival(factory) -> None:
    # Sequential A -> B on learner 10.
    with factory() as session:
        _add_learner(session, 10)
        _add_evaluation(
            session, evaluation_id=200, attempt_id=100, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=201, attempt_id=101, created_at=TB, bands=BANDS_B
        )
        session.commit()
    with factory() as session:
        apply_writing_evaluation(session, learner_id=10, writing_evaluation_id=200)
    with factory() as session:
        apply_writing_evaluation(session, learner_id=10, writing_evaluation_id=201)
    with factory() as session:
        sequential = _tr_state(session, 10).estimated_band

    # Late arrival B -> A on learner 11.
    with factory() as session:
        _add_learner(session, 11)
        _add_evaluation(
            session, evaluation_id=210, attempt_id=110, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=211, attempt_id=111, created_at=TB, bands=BANDS_B
        )
        session.commit()
    with factory() as session:
        apply_writing_evaluation(session, learner_id=11, writing_evaluation_id=211)
    with factory() as session:
        apply_writing_evaluation(session, learner_id=11, writing_evaluation_id=210)
    with factory() as session:
        late = _tr_state(session, 11).estimated_band

    # Concurrent on learner 12.
    with factory() as session:
        _add_learner(session, 12)
        _add_evaluation(
            session, evaluation_id=220, attempt_id=120, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=221, attempt_id=121, created_at=TB, bands=BANDS_B
        )
        session.commit()
    _run_concurrently(factory, [(12, 220), (12, 221)])
    with factory() as session:
        concurrent = _tr_state(session, 12).estimated_band

    assert sequential == Decimal("6.50")
    assert late == Decimal("6.50")
    assert concurrent == Decimal("6.50")
    assert sequential == late == concurrent
