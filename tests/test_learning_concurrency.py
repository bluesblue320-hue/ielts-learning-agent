"""P3-12 concurrency / idempotency hardening against real PostgreSQL.

These tests prove that concurrent applications cannot double-apply, corrupt
state, or let transaction completion order override canonical evidence order.
Controlled schedules additionally prove with real PostgreSQL wait-state
observation (``pg_stat_activity.wait_event_type = 'Lock'``) that the follower
backend is actually blocked on the owner's learner row lock before the owner
commits.
"""

import os
import threading
import time
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


# ---------------------------------------------------------------------------
# Controlled transaction/lock-completion schedules (final review hardening)
# ---------------------------------------------------------------------------


def _wait_until_backend_waits_on_lock(
    factory,
    backend_pid: int,
    timeout: float = 10.0,
) -> bool:
    """Poll PostgreSQL until the backend with ``backend_pid`` is demonstrably
    waiting on a lock.

    Uses a dedicated observer connection to inspect ``pg_stat_activity`` and
    returns ``True`` only when ``wait_event_type = 'Lock'`` is observed for
    that backend. A short bounded polling interval keeps the wait tight; on
    timeout it returns ``False`` so the caller fails the test explicitly.
    """

    deadline = time.monotonic() + timeout
    with factory() as observer:
        while time.monotonic() < deadline:
            wait_type = observer.execute(
                text(
                    "SELECT wait_event_type FROM pg_stat_activity "
                    "WHERE pid = :pid"
                ),
                {"pid": backend_pid},
            ).scalar()
            if wait_type == "Lock":
                return True
            time.sleep(0.02)
    return False


def _controlled_schedule(
    factory,
    *,
    learner_id: int,
    lock_owner_eval: int,
    follower_eval: int,
) -> tuple[list[int], bool]:
    """Deterministically make ``lock_owner_eval`` acquire the learner row lock
    first, then prove with PostgreSQL wait-state observation that the follower
    backend is actually blocked on that lock before the owner is released.

    Returns ``(completion_order, lock_wait_observed)``. ``lock_wait_observed``
    is ``True`` only when ``pg_stat_activity`` confirmed the follower backend
    waiting on a lock while the owner still held it.
    """

    owner_lock_acquired = threading.Event()
    release_owner = threading.Event()
    follower_ready = threading.Event()
    follower_backend_pid: list[int] = []
    completion: list[int] = []
    errors: list[BaseException] = []

    def owner() -> None:
        try:
            with factory() as session:
                # Acquire the learner row lock and KEEP the same transaction
                # open until apply runs; the service commits and releases it.
                session.execute(
                    select(Learner.id)
                    .where(Learner.id == learner_id)
                    .with_for_update()
                )
                owner_lock_acquired.set()
                assert release_owner.wait(timeout=15)
                apply_writing_evaluation(
                    session,
                    learner_id=learner_id,
                    writing_evaluation_id=lock_owner_eval,
                )
                completion.append(lock_owner_eval)
        except BaseException as error:  # pragma: no cover - failure must fail test
            errors.append(error)

    def follower() -> None:
        try:
            assert owner_lock_acquired.wait(timeout=15)
            with factory() as session:
                # Publish this backend's PostgreSQL PID, then call apply; the
                # apply must block on the owner's learner row lock. No
                # artificial sleep simulates waiting: the lock is the blocker.
                pid = session.execute(text("SELECT pg_backend_pid()")).scalar()
                follower_backend_pid.append(pid)
                follower_ready.set()
                apply_writing_evaluation(
                    session,
                    learner_id=learner_id,
                    writing_evaluation_id=follower_eval,
                )
                completion.append(follower_eval)
        except BaseException as error:  # pragma: no cover - failure must fail test
            errors.append(error)

    owner_thread = threading.Thread(target=owner)
    owner_thread.start()
    assert owner_lock_acquired.wait(timeout=15), (
        "owner never acquired the learner row lock"
    )

    follower_thread = threading.Thread(target=follower)
    follower_thread.start()
    assert follower_ready.wait(timeout=15), (
        "follower never published its backend pid"
    )

    # Central acceptance step: prove PostgreSQL sees the follower backend
    # blocked on a lock while the owner still holds the learner row lock.
    lock_wait_observed = _wait_until_backend_waits_on_lock(
        factory,
        follower_backend_pid[0],
    )

    release_owner.set()
    owner_thread.join(timeout=20)
    follower_thread.join(timeout=20)
    assert not owner_thread.is_alive() and not follower_thread.is_alive()
    assert not errors, errors
    return completion, lock_wait_observed


def test_controlled_schedule_a_first(factory) -> None:
    # Learner 20: A = evaluation 300 (attempt 200, older), B = 301 (attempt 201).
    with factory() as session:
        _add_learner(session, 20)
        _add_evaluation(
            session, evaluation_id=300, attempt_id=200, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=301, attempt_id=201, created_at=TB, bands=BANDS_B
        )
        session.commit()

    completion, lock_wait_observed = _controlled_schedule(
        factory, learner_id=20, lock_owner_eval=300, follower_eval=301
    )

    # PostgreSQL proved the follower (B) backend was blocked on the learner
    # lock before the owner (A) committed.
    assert lock_wait_observed is True
    assert completion == [300, 301]
    with factory() as session:
        state = _tr_state(session, 20)
        assert state.estimated_band == Decimal("6.50")
        assert state.evidence_count == 2
        assert state.revision == 2
        last = session.get(LearningEvidence, state.last_evidence_id)
        assert last.source_attempt_id == 201


def test_controlled_schedule_b_first(factory) -> None:
    # Learner 21: A = evaluation 310 (attempt 210, older), B = 311 (attempt 211).
    with factory() as session:
        _add_learner(session, 21)
        _add_evaluation(
            session, evaluation_id=310, attempt_id=210, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=311, attempt_id=211, created_at=TB, bands=BANDS_B
        )
        session.commit()

    completion, lock_wait_observed = _controlled_schedule(
        factory, learner_id=21, lock_owner_eval=311, follower_eval=310
    )

    # PostgreSQL proved the follower (A) backend was blocked on the learner
    # lock before the owner (B) committed.
    assert lock_wait_observed is True
    # Application/completion order is B then A, but canonical source order is
    # still A -> B, so the final state must equal canonical replay(A, B).
    assert completion == [311, 310]
    with factory() as session:
        state = _tr_state(session, 21)
        assert state.estimated_band == Decimal("6.50")
        assert state.evidence_count == 2
        assert state.revision == 2
        last = session.get(LearningEvidence, state.last_evidence_id)
        assert last.source_attempt_id == 211


def test_controlled_schedules_equal_canonical_replay(factory) -> None:
    # Sequential A -> B on learner 30.
    with factory() as session:
        _add_learner(session, 30)
        _add_evaluation(
            session, evaluation_id=400, attempt_id=300, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=401, attempt_id=301, created_at=TB, bands=BANDS_B
        )
        session.commit()
    with factory() as session:
        apply_writing_evaluation(session, learner_id=30, writing_evaluation_id=400)
    with factory() as session:
        apply_writing_evaluation(session, learner_id=30, writing_evaluation_id=401)
    with factory() as session:
        sequential = _tr_state(session, 30).estimated_band

    # Late B -> A on learner 31.
    with factory() as session:
        _add_learner(session, 31)
        _add_evaluation(
            session, evaluation_id=410, attempt_id=310, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=411, attempt_id=311, created_at=TB, bands=BANDS_B
        )
        session.commit()
    with factory() as session:
        apply_writing_evaluation(session, learner_id=31, writing_evaluation_id=411)
    with factory() as session:
        apply_writing_evaluation(session, learner_id=31, writing_evaluation_id=410)
    with factory() as session:
        late = _tr_state(session, 31).estimated_band

    # Controlled A-first on learner 32 (lock wait observed).
    with factory() as session:
        _add_learner(session, 32)
        _add_evaluation(
            session, evaluation_id=420, attempt_id=320, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=421, attempt_id=321, created_at=TB, bands=BANDS_B
        )
        session.commit()
    _, a_first_observed = _controlled_schedule(
        factory, learner_id=32, lock_owner_eval=420, follower_eval=421
    )
    assert a_first_observed is True
    with factory() as session:
        a_first = _tr_state(session, 32).estimated_band

    # Controlled B-first on learner 33 (lock wait observed).
    with factory() as session:
        _add_learner(session, 33)
        _add_evaluation(
            session, evaluation_id=430, attempt_id=330, created_at=TA, bands=BANDS_A
        )
        _add_evaluation(
            session, evaluation_id=431, attempt_id=331, created_at=TB, bands=BANDS_B
        )
        session.commit()
    _, b_first_observed = _controlled_schedule(
        factory, learner_id=33, lock_owner_eval=431, follower_eval=430
    )
    assert b_first_observed is True
    with factory() as session:
        b_first = _tr_state(session, 33).estimated_band

    assert sequential == Decimal("6.50")
    assert late == Decimal("6.50")
    assert a_first == Decimal("6.50")
    assert b_first == Decimal("6.50")
    assert sequential == late == a_first == b_first
