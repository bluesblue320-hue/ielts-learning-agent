"""Tests for the FastAPI application shell."""

import asyncio

from app.main import app, create_app


def test_application_factory_returns_configured_fastapi_app() -> None:
    application = create_app()

    assert application.title == "IELTS Learning Agent"
    assert application.version == "0.1.0"


def test_application_starts_in_test_context() -> None:
    async def start_application() -> None:
        async with app.router.lifespan_context(app):
            assert app.openapi()["info"]["title"] == "IELTS Learning Agent"

    asyncio.run(start_application())
