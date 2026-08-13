"""Unit tests for isolated PostgreSQL configuration guards."""

import pytest

from tests.support.database import validate_test_database_url


TEST_URL = "postgresql+psycopg://test-user@db:5432/ielts_test"
DEV_URL = "postgresql+psycopg://dev-user@db:5432/ielts_development"


def test_isolated_test_database_is_accepted() -> None:
    assert validate_test_database_url(TEST_URL, DEV_URL) == TEST_URL


def test_test_database_is_accepted_without_development_configuration() -> None:
    assert validate_test_database_url(TEST_URL) == TEST_URL


def test_non_test_database_name_is_rejected_without_leaking_url() -> None:
    with pytest.raises(ValueError) as captured:
        validate_test_database_url(DEV_URL)

    assert "isolated test database" in str(captured.value)
    assert "dev-user" not in str(captured.value)


def test_shared_test_and_development_url_is_rejected_without_leaking_url() -> None:
    with pytest.raises(ValueError) as captured:
        validate_test_database_url(TEST_URL, TEST_URL)

    assert "must not match" in str(captured.value)
    assert "test-user" not in str(captured.value)
