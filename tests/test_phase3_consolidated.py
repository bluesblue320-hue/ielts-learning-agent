"""P3-13 consolidated Phase 3 validation.

This module ties the complete deterministic Phase 3 path together against real
PostgreSQL:

    persisted WritingEvaluation
      -> apply
      -> exactly 4 evidence rows
      -> exactly 4 state rows
      -> exactly 1 planning decision (practice or no_practice)

It reuses the service/API and asserts the consolidated invariants that earlier
nodes prove individually: canonical-order replay, late arrival, idempotency,
cross-owner conflict, and concurrency equality. No live provider call occurs.
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
from sqlalchemy.orm import Session

from app.db.session import create_session_factory
from app.models.learning import (
    Learner,
    LearnerSkillState,
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
)
from app.models.writing import WritingAttempt, WritingEvaluation
from app.services.learning_application import (
    CrossOwnerConflictError,
    apply_writing_evaluation,
)
from tests.support.database import validate_test_database_url

TA = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
TB = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
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
    yield create_session_factory(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def _truncate(factory) -> None:
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


def _seed_learner(session: Session, learner_id: int = 1) -> None:
    session.add(Learner(id=learner_id, writing_target_band=Decimal("7.0")))


def _seed_pair(
    session: Session,
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


def _counts(session: Session) -> dict[str, int]:
    return {
        "updates": session.scalar(select(func.count()).select_from(LearningUpdate)),
        "evidence": session.scalar(select(func.count()).select_from(LearningEvidence)),
        "states": session.scalar(select(func.count()).select_from(LearnerSkillState)),
        "recommendations": session.scalar(
            select(func.count()).select_from(PracticeRecommendation)
        ),
    }


# ---------------------------------------------------------------------------
# Full path: evaluation -> apply -> 4 evidence -> 4 states -> 1 decision
# ---------------------------------------------------------------------------


def test_full_path_produces_exact_row_accounting(factory) -> None:
    with factory() as session:
        _seed_learner(session)
        _seed_pair(
            session,
            evaluation_id=200,
            attempt_id=100,
            created_at=TA,
            bands=BANDS_A,
        )
        session.commit()

    with factory() as session:
        result = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )
        assert result.recommendation.decision_type.value == "practice"
        assert result.recommendation.target_skill == "task_response"

        assert _counts(session) == {
            "updates": 1,
            "evidence": 4,
            "states": 4,
            "recommendations": 1,
        }
        # Exactly one recommendation for exactly one update.
        assert (
            session.scalar(
                select(func.count())
                .select_from(PracticeRecommendation)
                .join(LearningUpdate)
            )
            == 1
        )


def test_full_path_no_practice_persists_exactly_one_decision(factory) -> None:
    with factory() as session:
        _seed_learner(session)
        _seed_pair(
            session,
            evaluation_id=200,
            attempt_id=100,
            created_at=TA,
            bands=BANDS_B,  # all bands at/above the 7.0 target
        )
        session.commit()

    with factory() as session:
        result = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )
        assert result.recommendation.decision_type.value == "no_practice"
        assert result.recommendation.target_skill is None
        assert _counts(session) == {
            "updates": 1,
            "evidence": 4,
            "states": 4,
            "recommendations": 1,
        }
        recommendation = session.scalar(select(PracticeRecommendation))
        assert recommendation.decision_type == "no_practice"


# ---------------------------------------------------------------------------
# Canonical order equivalence: A->B == late B->A == concurrent
# ---------------------------------------------------------------------------


def _apply_sequential(factory, learner_id: int, order: list[int]) -> Decimal:
    for evaluation_id in order:
        with factory() as session:
            apply_writing_evaluation(
                session, learner_id=learner_id, writing_evaluation_id=evaluation_id
            )
    with factory() as session:
        return session.get(LearnerSkillState, (learner_id, "task_response")).estimated_band


def _apply_concurrent(factory, learner_id: int, evaluation_ids: list[int]) -> Decimal:
    barrier = threading.Barrier(len(evaluation_ids))

    def run(evaluation_id: int):
        barrier.wait()
        with factory() as session:
            apply_writing_evaluation(
                session, learner_id=learner_id, writing_evaluation_id=evaluation_id
            )

    with ThreadPoolExecutor(max_workers=len(evaluation_ids)) as pool:
        list(pool.map(run, evaluation_ids))
    with factory() as session:
        return session.get(LearnerSkillState, (learner_id, "task_response")).estimated_band


def test_canonical_order_equivalence_across_schedules(factory) -> None:
    # Sequential A -> B on learner 1.
    with factory() as session:
        _seed_learner(session, 1)
        _seed_pair(session, evaluation_id=200, attempt_id=100, created_at=TA, bands=BANDS_A)
        _seed_pair(session, evaluation_id=201, attempt_id=101, created_at=TB, bands=BANDS_B)
        session.commit()
    sequential = _apply_sequential(factory, 1, [200, 201])

    # Late arrival B -> A on learner 2.
    with factory() as session:
        _seed_learner(session, 2)
        _seed_pair(session, evaluation_id=210, attempt_id=110, created_at=TA, bands=BANDS_A)
        _seed_pair(session, evaluation_id=211, attempt_id=111, created_at=TB, bands=BANDS_B)
        session.commit()
    late = _apply_sequential(factory, 2, [211, 210])

    # Concurrent on learner 3.
    with factory() as session:
        _seed_learner(session, 3)
        _seed_pair(session, evaluation_id=220, attempt_id=120, created_at=TA, bands=BANDS_A)
        _seed_pair(session, evaluation_id=221, attempt_id=121, created_at=TB, bands=BANDS_B)
        session.commit()
    concurrent = _apply_concurrent(factory, 3, [220, 221])

    assert sequential == Decimal("6.50")
    assert late == Decimal("6.50")
    assert concurrent == Decimal("6.50")
    assert sequential == late == concurrent


# ---------------------------------------------------------------------------
# Idempotency and ownership through the full path
# ---------------------------------------------------------------------------


def test_consolidated_idempotency_and_cross_owner(factory) -> None:
    with factory() as session:
        _seed_learner(session, 1)
        _seed_pair(session, evaluation_id=200, attempt_id=100, created_at=TA, bands=BANDS_A)
        _seed_learner(session, 2)
        session.commit()

    with factory() as session:
        first = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )
    with factory() as session:
        second = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )
        assert second.reused is True
        assert second.learning_update_id == first.learning_update_id
        assert _counts(session) == {"updates": 1, "evidence": 4, "states": 4, "recommendations": 1}

    with factory() as session:
        with pytest.raises(CrossOwnerConflictError):
            apply_writing_evaluation(
                session, learner_id=2, writing_evaluation_id=200
            )
        assert _counts(session)["updates"] == 1
