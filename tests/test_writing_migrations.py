"""Integration coverage for the reversible Phase 2 writing migration."""

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.models import WritingAttempt, WritingEvaluation


WRITING_TABLES = {"writing_attempts", "writing_evaluations"}


def alembic_config(database_url: str | None = None) -> Config:
    config = Config("alembic.ini")
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def test_writing_revision_is_part_of_linear_history() -> None:
    script = ScriptDirectory.from_config(alembic_config())

    assert script.get_heads() == ["0006_recoverable_practice_submission_claims"]
    walk = {revision.revision: revision.down_revision for revision in script.walk_revisions()}
    assert walk["0006_recoverable_practice_submission_claims"] == "0005_planner_context_snapshot"
    assert walk["0005_planner_context_snapshot"] == "0004_writing_practice"
    assert walk["0004_writing_practice"] == "0003_learning"
    assert walk["0003_learning"] == "0002_writing"
    assert walk["0002_writing"] == "0001_phase1"


@pytest.mark.integration
def test_writing_migration_upgrades_downgrades_and_reupgrades(
    database_url: str,
) -> None:
    config = alembic_config(database_url)
    engine = create_engine(database_url)

    try:
        command.downgrade(config, "base")
        command.upgrade(config, "0001_phase1")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0001_phase1"
            )
            assert not WRITING_TABLES & set(inspect(connection).get_table_names())

        command.upgrade(config, "0002_writing")
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0002_writing"
            )
            assert WRITING_TABLES <= set(inspector.get_table_names())

            attempt_columns = {
                column["name"]
                for column in inspector.get_columns("writing_attempts")
            }
            evaluation_columns = {
                column["name"]
                for column in inspector.get_columns("writing_evaluations")
            }
            assert attempt_columns == set(
                WritingAttempt.__table__.columns.keys()
            )
            assert evaluation_columns == set(
                WritingEvaluation.__table__.columns.keys()
            )

            attempt_checks = {
                check["name"]
                for check in inspector.get_check_constraints("writing_attempts")
            }
            evaluation_checks = {
                check["name"]
                for check in inspector.get_check_constraints(
                    "writing_evaluations"
                )
            }
            assert attempt_checks >= {
                "ck_writing_attempt_question_nonblank",
                "ck_writing_attempt_essay_nonblank",
                "ck_writing_attempt_word_count_positive",
            }
            assert evaluation_checks >= {
                "ck_writing_evaluation_task_response_band",
                "ck_writing_evaluation_coherence_and_cohesion_band",
                "ck_writing_evaluation_lexical_resource_band",
                "ck_writing_evaluation_grammatical_range_and_accuracy_band",
                "ck_writing_evaluation_product_band",
                "ck_writing_evaluation_feedback_nonblank",
                "ck_writing_evaluation_provider_nonblank",
                "ck_writing_evaluation_model_nonblank",
                "ck_writing_evaluation_prompt_version_nonblank",
                "ck_writing_evaluation_rubric_version_nonblank",
                "ck_writing_evaluation_scoring_policy_version_nonblank",
                "ck_writing_evaluation_thinking_mode",
            }

            foreign_keys = inspector.get_foreign_keys("writing_evaluations")
            assert len(foreign_keys) == 1
            assert foreign_keys[0]["name"] == "fk_writing_evaluation_attempt_id"
            assert foreign_keys[0]["referred_table"] == "writing_attempts"
            assert foreign_keys[0]["constrained_columns"] == ["attempt_id"]
            assert foreign_keys[0]["options"]["ondelete"] == "CASCADE"

            unique_constraints = inspector.get_unique_constraints(
                "writing_evaluations"
            )
            assert {
                constraint["name"] for constraint in unique_constraints
            } >= {"uq_writing_evaluation_attempt_id"}
            assert {
                index["name"]
                for index in inspector.get_indexes("writing_attempts")
            } >= {"ix_writing_attempt_created_at"}
            assert {
                index["name"]
                for index in inspector.get_indexes("writing_evaluations")
            } >= {"ix_writing_evaluation_created_at"}

        command.downgrade(config, "0001_phase1")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0001_phase1"
            )
            assert not WRITING_TABLES & set(inspect(connection).get_table_names())

        command.upgrade(config, "0002_writing")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0002_writing"
            )
            assert WRITING_TABLES <= set(inspect(connection).get_table_names())
    finally:
        command.upgrade(config, "head")
        engine.dispose()
