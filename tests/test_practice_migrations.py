"""Integration coverage for the reversible Phase 4 writing practice migration."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base

PHASE3_TABLES = {
    "learners",
    "learning_updates",
    "learning_evidence",
    "learner_skill_states",
    "practice_recommendations",
}
PHASE2_TABLES = {"writing_attempts", "writing_evaluations"}

pytestmark = [pytest.mark.integration]


def alembic_config(database_url: str | None = None) -> Config:
    config = Config("alembic.ini")
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _version(engine) -> str:
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def _ensure_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


# ---------------------------------------------------------------------------
# Head / history (no database required)
# ---------------------------------------------------------------------------


def test_practice_revision_is_the_single_linear_head() -> None:
    script = ScriptDirectory.from_config(alembic_config())

    assert script.get_heads() == ["0006_recoverable_practice_submission_claims"]
    walk = {
        revision.revision: revision.down_revision
        for revision in script.walk_revisions()
    }
    assert walk["0006_recoverable_practice_submission_claims"] == "0005_planner_context_snapshot"
    assert walk["0005_planner_context_snapshot"] == "0004_writing_practice"
    assert walk["0004_writing_practice"] == "0003_learning"
    assert walk["0003_learning"] == "0002_writing"
    assert walk["0002_writing"] == "0001_phase1"
    assert walk["0001_phase1"] is None


# ---------------------------------------------------------------------------
# Real-PostgreSQL upgrade / downgrade / re-upgrade
# ---------------------------------------------------------------------------


def test_practice_migration_upgrades_downgrades_and_reupgrades(
    database_url: str,
) -> None:
    config = alembic_config(database_url)
    engine = create_engine(database_url)

    try:
        # base -> 0003_learning (no Phase 4 additions yet).
        command.downgrade(config, "base")
        command.upgrade(config, "0003_learning")
        assert _version(engine) == "0003_learning"
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            assert "writing_practices" not in tables
            assert PHASE3_TABLES <= tables
            unique_indexes = {
                index["name"]
                for index in inspect(connection).get_unique_constraints(
                    "practice_recommendations"
                )
            }
            assert "uq_practice_recommendation_id_learner" not in unique_indexes

        # 0003_learning -> 0004_writing_practice.
        command.upgrade(config, "head")
        assert _version(engine) == "0006_recoverable_practice_submission_claims"
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            assert "writing_practices" in tables
            assert PHASE3_TABLES <= tables
            assert PHASE2_TABLES <= tables
            # Phase 4 ownership candidate key added.
            unique_indexes = {
                index["name"]
                for index in inspector.get_unique_constraints(
                    "practice_recommendations"
                )
            }
            assert "uq_practice_recommendation_id_learner" in unique_indexes
            # writing_practices unique anchors.
            practice_uniques = {
                index["name"]
                for index in inspector.get_unique_constraints("writing_practices")
            }
            assert "uq_writing_practice_recommendation_id" in practice_uniques
            assert "uq_writing_practice_attempt_id" in practice_uniques
            practice_columns = {
                column["name"]
                for column in inspector.get_columns("writing_practices")
            }
            assert "submission_claimed_at" in practice_columns
            practice_checks = {
                check["name"]
                for check in inspector.get_check_constraints("writing_practices")
            }
            assert "ck_writing_practice_submission_state_matrix" in practice_checks
            # Composite ownership FK.
            fks = {
                (
                    fk["name"],
                    tuple(fk["constrained_columns"]),
                    tuple(fk["referred_columns"]),
                )
                for fk in inspector.get_foreign_keys("writing_practices")
            }
            assert (
                "fk_writing_practice_recommendation_ownership",
                ("recommendation_id", "learner_id"),
                ("id", "learner_id"),
            ) in fks

        # 0004_writing_practice -> 0003_learning (removes ONLY Phase 4).
        command.downgrade(config, "0003_learning")
        assert _version(engine) == "0003_learning"
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            assert "writing_practices" not in tables
            assert PHASE3_TABLES <= tables
            assert PHASE2_TABLES <= tables
            unique_indexes = {
                index["name"]
                for index in inspector.get_unique_constraints(
                    "practice_recommendations"
                )
            }
            assert "uq_practice_recommendation_id_learner" not in unique_indexes

        # 0003_learning -> 0004_writing_practice again (reproducibility).
        command.upgrade(config, "head")
        assert _version(engine) == "0006_recoverable_practice_submission_claims"
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            assert "writing_practices" in tables
    finally:
        command.upgrade(config, "head")
        engine.dispose()


def test_no_model_migration_drift_after_upgrade(database_url: str) -> None:
    _ensure_head(database_url)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            diffs = list(compare_metadata(migration_context, Base.metadata))
        assert diffs == []
    finally:
        engine.dispose()
