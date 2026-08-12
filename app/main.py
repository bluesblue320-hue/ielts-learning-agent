"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes.health import router as health_router


def create_app() -> FastAPI:
    """Build the Phase 1 API application without external side effects."""
    application = FastAPI(title="IELTS Learning Agent", version="0.1.0")
    application.include_router(health_router)
    return application


app = create_app()
