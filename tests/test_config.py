"""Tests for typed application configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/ielts_test"


def test_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IELTS_ENVIRONMENT", raising=False)
    monkeypatch.setenv("IELTS_DATABASE_URL", DATABASE_URL)

    settings = Settings(_env_file=None)

    assert settings.environment is Environment.DEVELOPMENT


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IELTS_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_environment_values_are_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IELTS_ENVIRONMENT", "test")
    monkeypatch.setenv("IELTS_DATABASE_URL", DATABASE_URL)

    settings = Settings(_env_file=None)

    assert settings.environment is Environment.TEST


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IELTS_ENVIRONMENT", "staging")
    monkeypatch.setenv("IELTS_DATABASE_URL", DATABASE_URL)

    with pytest.raises(ValidationError, match="environment"):
        Settings(_env_file=None)


def test_non_postgresql_database_url_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IELTS_DATABASE_URL", "sqlite:///local.db")

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_database_credentials_are_masked_in_settings_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IELTS_DATABASE_URL", DATABASE_URL)

    settings = Settings(_env_file=None)

    assert "password" not in repr(settings)
    assert "**********" in repr(settings)
