"""Integration tests for the Alembic baseline migration path."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

@pytest.mark.integration
def test_baseline_migration_upgrades_downgrades_and_reupgrades(
    database_url: str,
) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    command.downgrade(config, "base")
    command.upgrade(config, "0001_phase1")
    engine = create_engine(database_url)

    try:
        with engine.connect() as connection:
            version = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert version == "0001_phase1"

        command.downgrade(config, "base")
        with engine.connect() as connection:
            version_count = connection.scalar(text("SELECT count(*) FROM alembic_version"))
        assert version_count == 0
    finally:
        command.upgrade(config, "head")
        engine.dispose()
