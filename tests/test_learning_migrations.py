"""Integration coverage for the reversible Phase 3 learning migration."""

from datetime import datetime, timezone

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base
from app.models import (
    Learner,
    LearnerSkillState,
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
    WritingAttempt,
    WritingEvaluation,
)

PHASE3_TABLES = {
    "learners",
    "learning_updates",
    "learning_evidence",
    "learner_skill_states",
    "practice_recommendations",
}
PHASE2_TABLES = {"writing_attempts", "writing_evaluations"}


def alembic_config(database_url: str | None = None) -> Config:
    config = Config("alembic.ini")
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _version(engine: object) -> str:
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def _ensure_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


# ---------------------------------------------------------------------------
# Head / history (no database required)
# ---------------------------------------------------------------------------


def test_phase3_revision_is_the_single_linear_head() -> None:
    script = ScriptDirectory.from_config(alembic_config())

    assert script.get_heads() == ["0003_learning"]
    walk = {revision.revision: revision.down_revision for revision in script.walk_revisions()}
    assert walk["0003_learning"] == "0002_writing"
    assert walk["0002_writing"] == "0001_phase1"
    assert walk["0001_phase1"] is None


# ---------------------------------------------------------------------------
# Full migration cycle
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_learning_migration_upgrades_downgrades_and_reupgrades(
    database_url: str,
) -> None:
    config = alembic_config(database_url)
    engine = create_engine(database_url)

    try:
        command.downgrade(config, "base")
        command.upgrade(config, "0002_writing")
        with engine.connect() as connection:
            assert _version(engine) == "0002_writing"
            assert not PHASE3_TABLES & set(inspect(connection).get_table_names())
            assert PHASE2_TABLES <= set(inspect(connection).get_table_names())

        # 0002_writing -> 0003_learning
        command.upgrade(config, "head")
        assert _version(engine) == "0003_learning"
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            assert PHASE3_TABLES <= tables
            assert PHASE2_TABLES <= tables

            for model in (
                Learner,
                LearningUpdate,
                LearningEvidence,
                LearnerSkillState,
                PracticeRecommendation,
            ):
                columns = {
                    column["name"]
                    for column in inspector.get_columns(model.__tablename__)
                }
                assert columns == set(model.__table__.columns.keys())

            learners_types = {
                column["name"]: column["type"]
                for column in inspector.get_columns("learners")
            }
            assert str(learners_types["writing_target_band"]) == "NUMERIC(2, 1)"
            assert "TIMESTAMP" in str(learners_types["created_at"])

            evidence_types = {
                column["name"]: column["type"]
                for column in inspector.get_columns("learning_evidence")
            }
            assert str(evidence_types["observed_band"]) == "NUMERIC(2, 1)"

            state_types = {
                column["name"]: column["type"]
                for column in inspector.get_columns("learner_skill_states")
            }
            assert str(state_types["estimated_band"]) == "NUMERIC(3, 2)"

            recommendation_types = {
                column["name"]: column["type"]
                for column in inspector.get_columns("practice_recommendations")
            }
            assert str(recommendation_types["current_estimate"]) == "NUMERIC(3, 2)"
            assert "JSONB" in str(recommendation_types["reason_codes"])
            assert "JSONB" in str(recommendation_types["state_snapshot"])

        # 0003_learning -> 0002_writing
        command.downgrade(config, "0002_writing")
        assert _version(engine) == "0002_writing"
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            assert not PHASE3_TABLES & tables
            assert PHASE2_TABLES <= tables

        # 0002_writing -> 0003_learning again (reproducibility)
        command.upgrade(config, "head")
        assert _version(engine) == "0003_learning"
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            assert PHASE3_TABLES <= tables
            replay_index = {
                index["name"]
                for index in inspect(connection).get_indexes("learning_evidence")
            }
            assert "ix_learning_evidence_canonical_replay" in replay_index
    finally:
        command.upgrade(config, "head")
        engine.dispose()


# ---------------------------------------------------------------------------
# Model <-> migration drift
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_no_model_migration_drift_after_upgrade(database_url: str) -> None:
    _ensure_head(database_url)
    engine = create_engine(database_url)

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        differences = list(compare_metadata(context, Base.metadata))

    assert differences == []
    engine.dispose()


# ---------------------------------------------------------------------------
# Actual constraint inspection on the migrated schema
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_migrated_schema_contains_accepted_constraints(database_url: str) -> None:
    _ensure_head(database_url)
    engine = create_engine(database_url)

    with engine.connect() as connection:
        inspector = inspect(connection)

        learner_checks = {
            check["name"]
            for check in inspector.get_check_constraints("learners")
        }
        assert "ck_learner_writing_target_band" in learner_checks

        update_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("learning_updates")
        }
        assert {
            "uq_learning_update_learner_identity",
            "uq_learning_update_identity",
        } <= update_uniques
        assert any(
            constraint["name"] == "uq_learning_update_writing_evaluation_id"
            for constraint in inspector.get_unique_constraints("learning_updates")
        ) or {
            "writing_evaluation_id"
            for constraint in inspector.get_unique_constraints("learning_updates")
            if {column["name"] for column in constraint["column_names"]}
            == {"writing_evaluation_id"}
        }

        evidence_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("learning_evidence")
        }
        assert {
            "uq_learning_evidence_update_skill",
            "uq_learning_evidence_identity",
        } <= evidence_uniques
        evidence_checks = {
            check["name"]
            for check in inspector.get_check_constraints("learning_evidence")
        }
        assert "ck_learning_evidence_skill" in evidence_checks
        assert "ck_learning_evidence_observed_band" in evidence_checks
        evidence_fks = {
            foreign_key["name"]
            for foreign_key in inspector.get_foreign_keys("learning_evidence")
        }
        assert {
            "fk_learning_evidence_learning_update_ownership",
            "fk_learning_evidence_source_attempt_id",
        } <= evidence_fks
        replay_indexes = {
            index["name"]
            for index in inspector.get_indexes("learning_evidence")
        }
        assert "ix_learning_evidence_canonical_replay" in replay_indexes

        state_pk = inspector.get_pk_constraint("learner_skill_states")
        assert set(state_pk["constrained_columns"]) == {"learner_id", "skill"}
        state_checks = {
            check["name"]
            for check in inspector.get_check_constraints("learner_skill_states")
        }
        assert "ck_learner_skill_state_observed_consistency" in state_checks
        state_fks = {
            foreign_key["name"]
            for foreign_key in inspector.get_foreign_keys("learner_skill_states")
        }
        assert "fk_learner_skill_state_last_evidence_ownership" in state_fks

        recommendation_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(
                "practice_recommendations"
            )
        }
        assert "uq_practice_recommendation_learning_update_id" in recommendation_uniques
        recommendation_checks = {
            check["name"]
            for check in inspector.get_check_constraints("practice_recommendations")
        }
        assert {
            "ck_practice_recommendation_decision_type",
            "ck_practice_recommendation_reason_sequences",
            "ck_practice_recommendation_target_band_nullability",
            "ck_practice_recommendation_snapshot_skills",
            "ck_practice_recommendation_decision_shape",
        } <= recommendation_checks
        recommendation_fks = {
            foreign_key["name"]
            for foreign_key in inspector.get_foreign_keys(
                "practice_recommendations"
            )
        }
        assert {
            "fk_practice_recommendation_learning_update_ownership",
            "fk_practice_recommendation_learner_id",
        } <= recommendation_fks

    engine.dispose()


# ---------------------------------------------------------------------------
# Representative real-PostgreSQL constraint enforcement
# ---------------------------------------------------------------------------


def _fixture_tables(connection: object) -> None:
    connection.execute(
        Learner.__table__.insert().values(id=1, writing_target_band="7.0")
    )
    connection.execute(
        Learner.__table__.insert().values(id=2, writing_target_band="7.0")
    )
    connection.execute(
        WritingAttempt.__table__.insert().values(
            id=100, question="Q", essay="E", word_count=1
        )
    )
    connection.execute(
        WritingEvaluation.__table__.insert().values(
            id=200,
            attempt_id=100,
            task_response_band="6.5",
            coherence_and_cohesion_band="6.5",
            lexical_resource_band="6.5",
            grammatical_range_and_accuracy_band="6.5",
            product_band="6.5",
            criteria_feedback={"task_response": {}},
            strengths=["s"],
            weaknesses=["w"],
            error_tags=[],
            recommended_skills=[],
            feedback="f",
            provider="p",
            model="m",
            prompt_version="pv",
            rubric_version="rv",
            scoring_policy_version="sv",
            thinking_mode="disabled",
        )
    )
    connection.execute(
        LearningUpdate.__table__.insert().values(
            id=10,
            learner_id=1,
            writing_evaluation_id=200,
            skill_taxonomy_version="writing-core-v1",
            state_policy_version="writing-state-ewma-v1",
            planner_version="writing-practice-gap-v1",
        )
    )


def _valid_evidence(skill: str = "task_response", learner_id: int = 1) -> dict:
    return {
        "learning_update_id": 10,
        "learner_id": learner_id,
        "writing_evaluation_id": 200,
        "skill": skill,
        "observed_band": "6.5",
        "source_created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "source_attempt_id": 100,
        "provider": "p",
        "model": "m",
        "prompt_version": "pv",
        "rubric_version": "rv",
        "scoring_policy_version": "sv",
        "thinking_mode": "disabled",
    }


@pytest.mark.integration
def test_database_rejects_recommendation_of_another_learner(
    database_url: str,
) -> None:
    _ensure_head(database_url)
    engine = create_engine(database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        _fixture_tables(connection)
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    PracticeRecommendation.__table__.insert().values(
                        id=1,
                        learning_update_id=10,
                        learner_id=2,
                        decision_type="no_practice",
                        target_skill=None,
                        learner_target_band="7.0",
                        current_estimate=None,
                        reason_codes='["cold_start"]',
                        planner_version="writing-practice-gap-v1",
                        state_snapshot="{}",
                    )
                )
        transaction.rollback()
    finally:
        connection.close()
        engine.dispose()


@pytest.mark.integration
def test_database_rejects_evidence_with_inconsistent_ownership(
    database_url: str,
) -> None:
    _ensure_head(database_url)
    engine = create_engine(database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        _fixture_tables(connection)
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    LearningEvidence.__table__.insert().values(
                        id=1, **_valid_evidence(learner_id=2)
                    )
                )
        transaction.rollback()
    finally:
        connection.close()
        engine.dispose()


@pytest.mark.integration
def test_database_rejects_invalid_canonical_skill(database_url: str) -> None:
    _ensure_head(database_url)
    engine = create_engine(database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        _fixture_tables(connection)
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    LearningEvidence.__table__.insert().values(
                        id=2, **_valid_evidence(skill="grammar")
                    )
                )
        transaction.rollback()
    finally:
        connection.close()
        engine.dispose()


@pytest.mark.integration
def test_database_rejects_invalid_practice_decision_shape(database_url: str) -> None:
    _ensure_head(database_url)
    engine = create_engine(database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        _fixture_tables(connection)
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    PracticeRecommendation.__table__.insert().values(
                        id=2,
                        learning_update_id=10,
                        learner_id=1,
                        decision_type="practice",
                        target_skill=None,
                        learner_target_band="7.0",
                        current_estimate="6.0",
                        reason_codes='["largest_target_gap"]',
                        planner_version="writing-practice-gap-v1",
                        state_snapshot="{}",
                    )
                )
        transaction.rollback()
    finally:
        connection.close()
        engine.dispose()
