"""API tests for liveness and database readiness."""

import asyncio
from collections.abc import Generator
from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session, get_engine, get_session_factory
from app.main import create_app


async def get(application: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


def test_liveness_does_not_require_database_configuration() -> None:
    application = create_app()

    response = asyncio.run(get(application, "/health/live"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ielts-learning-agent",
    }


def test_readiness_reports_available_database() -> None:
    application = create_app()
    session = Mock(spec=Session)

    def override_session() -> Generator[Session, None, None]:
        yield session

    application.dependency_overrides[get_db_session] = override_session
    try:
        response = asyncio.run(get(application, "/health/ready"))
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "available",
    }
    session.execute.assert_called_once()


def test_readiness_reports_dependency_failure_without_leaking_details() -> None:
    application = create_app()
    session = Mock(spec=Session)
    session.execute.side_effect = SQLAlchemyError("private connection details")

    def override_session() -> Generator[Session, None, None]:
        yield session

    application.dependency_overrides[get_db_session] = override_session
    try:
        response = asyncio.run(get(application, "/health/ready"))
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
    }
    assert "private connection details" not in response.text


@pytest.mark.integration
def test_readiness_connects_to_postgresql(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IELTS_DATABASE_URL", database_url)
    get_settings.cache_clear()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    application = create_app()
    try:
        response = asyncio.run(get(application, "/health/ready"))
    finally:
        if get_engine.cache_info().currsize:
            get_engine().dispose()
        get_session_factory.cache_clear()
        get_engine.cache_clear()
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "available",
    }
