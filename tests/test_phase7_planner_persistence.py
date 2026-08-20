"""Focused P7-04 persistence and migration coverage."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import JSONB

import app.models  # noqa: F401  (register every ORM model on Base.metadata)
from app.db.base import Base
from app.models import PracticeRecommendation


REVISION = "0005_planner_context_snapshot"
PREVIOUS_REVISION = "0004_writing_practice"
COLUMN = "planner_context_snapshot"
CHECK = "ck_practice_recommendation_planner_context_snapshot_object"


def _config(database_url: str | None = None) -> Config:
    config = Config("alembic.ini")
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _version(engine: object) -> str:
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def test_phase7_revision_is_single_linear_head() -> None:
    script = ScriptDirectory.from_config(_config())
    walk = {revision.revision: revision.down_revision for revision in script.walk_revisions()}

    assert script.get_heads() == [REVISION]
    assert walk[REVISION] == PREVIOUS_REVISION


def test_snapshot_column_is_nullable_jsonb_with_narrow_object_check() -> None:
    table = PracticeRecommendation.__table__
    column = table.c[COLUMN]
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }

    assert isinstance(column.type, JSONB)
    assert column.nullable is True
    assert checks[CHECK] == (
        "planner_context_snapshot IS NULL OR "
        "jsonb_typeof(planner_context_snapshot) = 'object'"
    )
    assert "planner_version" not in checks[CHECK]
    assert "reason_codes" not in checks[CHECK]


@pytest.mark.integration
def test_phase7_migration_upgrades_downgrades_and_preserves_tables(
    database_url: str,
) -> None:
    config = _config(database_url)
    engine = create_engine(database_url)

    try:
        command.upgrade(config, "head")
        command.downgrade(config, PREVIOUS_REVISION)
        assert _version(engine) == PREVIOUS_REVISION
        with engine.connect() as connection:
            before_tables = set(inspect(connection).get_table_names())
            before_columns = {
                column["name"]
                for column in inspect(connection).get_columns(
                    "practice_recommendations"
                )
            }
            assert COLUMN not in before_columns

        command.upgrade(config, REVISION)
        assert _version(engine) == REVISION
        with engine.connect() as connection:
            inspector = inspect(connection)
            after_columns = {
                column["name"]: column for column in inspector.get_columns(
                    "practice_recommendations"
                )
            }
            checks = {
                check["name"]: check["sqltext"]
                for check in inspector.get_check_constraints(
                    "practice_recommendations"
                )
            }
            assert set(inspector.get_table_names()) == before_tables
            assert after_columns[COLUMN]["nullable"] is True
            assert "JSONB" in str(after_columns[COLUMN]["type"])
            assert CHECK in checks
            assert "planner_context_snapshot IS NULL" in checks[CHECK]
            assert "jsonb_typeof(planner_context_snapshot) = 'object'" in checks[CHECK]

        command.downgrade(config, PREVIOUS_REVISION)
        assert _version(engine) == PREVIOUS_REVISION
        with engine.connect() as connection:
            final_columns = {
                column["name"]
                for column in inspect(connection).get_columns(
                    "practice_recommendations"
                )
            }
            assert COLUMN not in final_columns
    finally:
        command.upgrade(config, "head")
        engine.dispose()


@pytest.mark.integration
def test_phase7_head_matches_orm_metadata(database_url: str) -> None:
    command.upgrade(_config(database_url), "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            differences = list(compare_metadata(context, Base.metadata))
        assert differences == []
    finally:
        engine.dispose()
