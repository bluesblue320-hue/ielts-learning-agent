"""Shared deterministic test configuration and integration fixtures."""

import os
from typing import Any

import pytest

from app.llm.deepseek import DeepSeekProvider


TEST_DATABASE_URL_ENV = "IELTS_TEST_DATABASE_URL"
DEEPSEEK_API_KEY_ENV = "IELTS_DEEPSEEK_API_KEY"


@pytest.fixture(autouse=True)
def isolate_live_provider_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove credentials and reject provider calls without a mock client."""

    monkeypatch.delenv(DEEPSEEK_API_KEY_ENV, raising=False)
    original_send = DeepSeekProvider._send

    async def guarded_send(
        provider: DeepSeekProvider,
        payload: dict[str, object],
    ) -> Any:
        if provider._client is None:
            raise AssertionError(
                "Live provider HTTP is disabled in the deterministic test suite."
            )
        return await original_send(provider, payload)

    monkeypatch.setattr(DeepSeekProvider, "_send", guarded_send)


@pytest.fixture
def database_url() -> str:
    url = os.getenv(TEST_DATABASE_URL_ENV)
    if url is None:
        pytest.skip(f"{TEST_DATABASE_URL_ENV} is required for PostgreSQL integration")
    return url
