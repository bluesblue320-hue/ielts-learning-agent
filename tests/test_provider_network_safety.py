"""Safety checks for deterministic provider tests."""

import asyncio
import os

import pytest
from pydantic import SecretStr

from app.llm import DeepSeekProvider, DeepSeekSettings


pytestmark = pytest.mark.provider


def test_suite_removes_deepseek_credential_from_test_environment() -> None:
    assert "IELTS_DEEPSEEK_API_KEY" not in os.environ


def test_suite_blocks_deepseek_provider_without_mock_http_client() -> None:
    provider = DeepSeekProvider(
        DeepSeekSettings(
            api_key=SecretStr("deterministic-test-placeholder"),
            api_url="https://api.deepseek.test/chat/completions",
            model="test-model",
        )
    )

    with pytest.raises(
        AssertionError,
        match="Live provider HTTP is disabled",
    ):
        asyncio.run(provider._send({}))
