"""Shared pytest fixtures for foundation integration tests."""

import os

import pytest


TEST_DATABASE_URL_ENV = "IELTS_TEST_DATABASE_URL"


@pytest.fixture
def database_url() -> str:
    url = os.getenv(TEST_DATABASE_URL_ENV)
    if url is None:
        pytest.skip(f"{TEST_DATABASE_URL_ENV} is required for PostgreSQL integration")
    return url
