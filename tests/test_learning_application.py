"""Real-PostgreSQL integration tests for the P3-10 atomic application service."""

import os
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
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
from app.schemas.planning import DecisionType
from app.services.learning_application import (
    CrossOwnerConflictError,
    EvaluationNotFoundError,
    IDEMPOTENCY_CONSTRAINT,
    LearningPersistenceError,
    LearningSourceError,
    LearnerNotFoundError,
    AppliedLearningResult,
    _violated_constraint,
    apply_writing_evaluation,
)
from tests.support.database import validate_test_database_url

DT = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _integrity_error(constraint_name: str | None) -> IntegrityError:
    """Build a fake IntegrityError carrying structured PostgreSQL diagnostics."""
    diag = SimpleNamespace(constraint_name=constraint_name)
    return IntegrityError("INSERT ...", {}, SimpleNamespace(diag=diag))


def _no_diag_integrity_error() -> IntegrityError:
    """Build an IntegrityError whose driver origin exposes no diagnostics."""
    return IntegrityError("INSERT ...", {}, SimpleNamespace())


def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="module")
def session_factory():
    url = os.getenv("IELTS_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("IELTS_TEST_DATABASE_URL is required for PostgreSQL integration")
    validate_test_database_url(url, os.getenv("IELTS_DATABASE_URL"))
    engine = create_engine(url)
    command.upgrade(alembic_config(url), "head")
    factory = create_session_factory(engine)
    yield factory
    engine.dispose()


def _cleanup(session: Session) -> None:
    """Remove Phase 3 rows and Phase 2 fixtures in FK-safe reverse order."""
    session.execute(delete(PracticeRecommendation))
    session.execute(delete(LearnerSkillState))
    session.execute(delete(LearningEvidence))
    session.execute(delete(LearningUpdate))
    session.execute(delete(Learner))
    session.execute(delete(WritingEvaluation))
    session.execute(delete(WritingAttempt))
    session.commit()


def _add_learner(session: Session, learner_id: int, target: str = "7.0") -> None:
    session.add(Learner(id=learner_id, writing_target_band=Decimal(target)))


def _add_attempt(
    session: Session,
    *,
    attempt_id: int,
    created_at: datetime = DT,
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


def _add_evaluation(
    session: Session,
    *,
    evaluation_id: int,
    attempt_id: int,
    bands: dict[str, str],
    created_at: datetime = DT,
) -> None:
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
            model="deepseek-chat",
            prompt_version="writing-v2",
            rubric_version="writing-task2-v1",
            scoring_policy_version="writing-scoring-v1",
            thinking_mode="disabled",
            created_at=created_at,
        )
    )


def _counts(session: Session) -> dict[str, int]:
    return {
        "updates": session.scalar(select(func.count()).select_from(LearningUpdate)),
        "evidence": session.scalar(
            select(func.count()).select_from(LearningEvidence)
        ),
        "states": session.scalar(
            select(func.count()).select_from(LearnerSkillState)
        ),
        "recommendations": session.scalar(
            select(func.count()).select_from(PracticeRecommendation)
        ),
    }


# ---------------------------------------------------------------------------
# First apply and exact row accounting
# ---------------------------------------------------------------------------


def test_first_apply_creates_exact_phase3_rows(session_factory) -> None:
    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        result = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )

        assert result.reused is False
        assert result.recommendation.decision_type == DecisionType.PRACTICE
        assert result.recommendation.target_skill == "task_response"
        assert _counts(session) == {
            "updates": 1,
            "evidence": 4,
            "states": 4,
            "recommendations": 1,
        }
        update = session.scalar(select(LearningUpdate))
        assert update.learner_id == 1
        assert update.writing_evaluation_id == 200
        assert update.skill_taxonomy_version == "writing-core-v1"
        assert update.state_policy_version == "writing-state-ewma-v1"
        assert update.planner_version == "writing-practice-gap-v1"
        skills = {
            row.skill for row in session.scalars(select(LearningEvidence)).all()
        }
        assert skills == {
            "task_response",
            "coherence_and_cohesion",
            "lexical_resource",
            "grammatical_range_and_accuracy",
        }
        state = session.get(LearnerSkillState, (1, "task_response"))
        assert state.estimated_band == Decimal("6.00")
        assert state.evidence_count == 1
        assert state.revision == 1
        _cleanup(session)


def test_no_practice_outcome_persists_exactly_one_decision(session_factory) -> None:
    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1, target="6.0")
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.5",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "7.0",
                "grammatical_range_and_accuracy": "7.0",
            },
        )
        session.commit()

        result = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )

        assert result.recommendation.decision_type == DecisionType.NO_PRACTICE
        assert result.recommendation.target_skill is None
        rows = session.scalars(select(PracticeRecommendation)).all()
        assert len(rows) == 1
        assert rows[0].decision_type == "no_practice"
        # Single evaluation means evidence_count == 1 < 3 for every skill, so
        # the policy appends the insufficient_evidence qualifier (P3-08
        # example E).
        assert rows[0].reason_codes == ["target_achieved", "insufficient_evidence"]
        assert set(rows[0].state_snapshot) == {
            "task_response",
            "coherence_and_cohesion",
            "lexical_resource",
            "grammatical_range_and_accuracy",
        }
        _cleanup(session)


# ---------------------------------------------------------------------------
# Idempotency / cross-owner
# ---------------------------------------------------------------------------


def test_idempotent_replay_returns_existing_without_duplicate_effects(
    session_factory,
) -> None:
    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        first = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )
        counts_after_first = _counts(session)
        state_revision = session.get(
            LearnerSkillState, (1, "task_response")
        ).revision

        second = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )

        assert second.reused is True
        assert second.learning_update_id == first.learning_update_id
        assert second.recommendation == first.recommendation
        assert _counts(session) == counts_after_first
        assert (
            session.get(LearnerSkillState, (1, "task_response")).revision
            == state_revision
        )
        _cleanup(session)


def test_cross_owner_reuse_is_explicit_conflict(session_factory) -> None:
    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_learner(session, 2)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)
        with pytest.raises(CrossOwnerConflictError):
            apply_writing_evaluation(
                session, learner_id=2, writing_evaluation_id=200
            )
        # Learner 2 must have no Phase 3 rows of its own.
        assert (
            session.scalar(
                select(func.count())
                .select_from(LearningUpdate)
                .where(LearningUpdate.learner_id == 2)
            )
            == 0
        )
        _cleanup(session)


# ---------------------------------------------------------------------------
# Not found / source errors and rollback
# ---------------------------------------------------------------------------


def test_learner_not_found(session_factory) -> None:
    with session_factory() as session:
        _cleanup(session)
        with pytest.raises(LearnerNotFoundError):
            apply_writing_evaluation(session, learner_id=999, writing_evaluation_id=200)
        assert _counts(session)["updates"] == 0


def test_evaluation_not_found(session_factory) -> None:
    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        session.commit()
        with pytest.raises(EvaluationNotFoundError):
            apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=999)
        assert _counts(session)["updates"] == 0


def test_mid_transaction_failure_rolls_back_all_phase3_writes(
    session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.learning_application as service_module
    from app.learner.state_engine import WritingStateReplayError

    def boom(items, *, state_policy_version):
        raise WritingStateReplayError("injected mid-transaction failure")

    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        monkeypatch.setattr(
            service_module, "rebuild_all_skill_states", boom
        )
        with pytest.raises(WritingStateReplayError, match="injected"):
            apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)
        assert _counts(session) == {
            "updates": 0,
            "evidence": 0,
            "states": 0,
            "recommendations": 0,
        }
        _cleanup(session)


def test_source_extraction_failure_leaves_no_partial_rows(
    session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.learning_application as service_module
    from app.learner.writing_evidence import WritingEvidenceExtractionError

    def failing_extract(evaluation, attempt):
        raise WritingEvidenceExtractionError("injected extraction failure")

    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        monkeypatch.setattr(
            service_module, "extract_writing_evidence", failing_extract
        )
        with pytest.raises(LearningSourceError):
            apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)
        assert _counts(session) == {
            "updates": 0,
            "evidence": 0,
            "states": 0,
            "recommendations": 0,
        }
        _cleanup(session)


# ---------------------------------------------------------------------------
# Late-arriving older evidence rebuilds to canonical order
# ---------------------------------------------------------------------------


def test_late_older_evidence_rebuilds_to_canonical_replay(session_factory) -> None:
    t_a = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)  # older
    t_b = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)  # newer
    bands_a = {
        "task_response": "6.0",
        "coherence_and_cohesion": "6.5",
        "lexical_resource": "6.5",
        "grammatical_range_and_accuracy": "6.5",
    }
    bands_b = {
        "task_response": "7.0",
        "coherence_and_cohesion": "7.0",
        "lexical_resource": "7.0",
        "grammatical_range_and_accuracy": "7.0",
    }

    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100, created_at=t_a)
        _add_attempt(session, attempt_id=101, created_at=t_b)
        _add_evaluation(session, evaluation_id=200, attempt_id=100, bands=bands_a, created_at=t_a)
        _add_evaluation(session, evaluation_id=201, attempt_id=101, bands=bands_b, created_at=t_b)
        session.commit()

        # Apply the NEWER evaluation first, then the late older one.
        apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=201)
        apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)

        expected = {
            "task_response": Decimal("6.50"),
            "coherence_and_cohesion": Decimal("6.75"),
            "lexical_resource": Decimal("6.75"),
            "grammatical_range_and_accuracy": Decimal("6.75"),
        }
        for skill, band in expected.items():
            state = session.get(LearnerSkillState, (1, skill))
            assert state.estimated_band == band
            assert state.evidence_count == 2
            assert state.revision == 2
        # Canonical last evidence for every skill is the newer attempt 101.
        for skill in expected:
            state = session.get(LearnerSkillState, (1, skill))
            evidence = session.get(LearningEvidence, state.last_evidence_id)
            assert evidence.source_attempt_id == 101
        _cleanup(session)


def test_phase2_rows_unchanged_after_apply(session_factory) -> None:
    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        attempt_before = session.get(WritingAttempt, 100)
        evaluation_before = session.get(WritingEvaluation, 200)
        apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)

        attempt_after = session.get(WritingAttempt, 100)
        evaluation_after = session.get(WritingEvaluation, 200)
        assert attempt_after.essay == attempt_before.essay
        assert attempt_after.created_at == attempt_before.created_at
        assert evaluation_after.task_response_band == evaluation_before.task_response_band
        assert evaluation_after.provider == evaluation_before.provider
        _cleanup(session)


# ---------------------------------------------------------------------------
# Persistence failure boundary (final review hardening)
# ---------------------------------------------------------------------------


def test_violated_constraint_reads_structured_diagnostics() -> None:
    assert _violated_constraint(_integrity_error(IDEMPOTENCY_CONSTRAINT)) == (
        IDEMPOTENCY_CONSTRAINT
    )
    assert _violated_constraint(_integrity_error("uq_other")) == "uq_other"


def test_violated_constraint_is_defensive_without_diagnostics() -> None:
    assert _violated_constraint(_no_diag_integrity_error()) is None


def test_idempotency_constraint_name_matches_migration() -> None:
    # The frozen idempotency anchor must equal the named unique constraint on
    # learning_updates.writing_evaluation_id as materialized by the accepted
    # migration (the database-enforced authority).
    import pathlib

    migration = pathlib.Path(
        "migrations/versions/0003_learning_phase3_tables.py"
    ).read_text(encoding="utf-8")
    assert f'name="{IDEMPOTENCY_CONSTRAINT}"' in migration


def test_accepted_idempotency_constraint_enters_duplicate_resolution(
    session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.learning_application as service_module

    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        calls: list[dict] = []
        canned = AppliedLearningResult(
            learning_update_id=1,
            recommendation_id=1,
            recommendation=None,  # type: ignore[arg-type]
            reused=True,
        )

        def fake_resolve(_session, *, learner_id, writing_evaluation_id):
            calls.append(
                {"learner_id": learner_id, "evaluation_id": writing_evaluation_id}
            )
            return canned

        def failing_commit(*_args, **_kwargs):
            raise _integrity_error(IDEMPOTENCY_CONSTRAINT)

        monkeypatch.setattr(service_module, "_resolve_existing", fake_resolve)
        monkeypatch.setattr(session, "commit", failing_commit)

        result = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )

        assert result.reused is True
        assert calls == [{"learner_id": 1, "evaluation_id": 200}]
        assert not session.in_transaction()


def test_non_idempotency_integrity_error_becomes_persistence_error(
    session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.learning_application as service_module

    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        resolve_calls: list = []

        def fake_resolve(*_args, **_kwargs):
            resolve_calls.append("unexpected")

        def failing_commit(*_args, **_kwargs):
            raise _integrity_error("uq_learning_evidence_update_skill")

        monkeypatch.setattr(service_module, "_resolve_existing", fake_resolve)
        monkeypatch.setattr(session, "commit", failing_commit)

        with pytest.raises(LearningPersistenceError):
            apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)
        # Duplicate resolution must NOT be entered for a foreign constraint.
        assert resolve_calls == []
        # Rollback occurred: session is no longer inside a transaction.
        assert not session.in_transaction()
        assert _counts(session)["updates"] == 0


def test_general_sqlalchemy_error_becomes_persistence_error(
    session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_factory() as session:
        _cleanup(session)
        _add_learner(session, 1)
        _add_attempt(session, attempt_id=100)
        _add_evaluation(
            session,
            evaluation_id=200,
            attempt_id=100,
            bands={
                "task_response": "6.0",
                "coherence_and_cohesion": "6.5",
                "lexical_resource": "6.5",
                "grammatical_range_and_accuracy": "6.5",
            },
        )
        session.commit()

        def failing_commit(*_args, **_kwargs):
            raise OperationalError("UPDATE ...", {}, Exception("boom"))

        monkeypatch.setattr(session, "commit", failing_commit)

        with pytest.raises(LearningPersistenceError):
            apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=200)
        assert not session.in_transaction()
        assert _counts(session)["updates"] == 0
