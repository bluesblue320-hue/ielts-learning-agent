"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.routes.health import router as health_router
from app.api.routes.writing import router as writing_router


def create_app() -> FastAPI:
    """Build the API application without opening external connections."""
    application = FastAPI(title="IELTS Learning Agent", version="0.1.0")
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(writing_router)
    return application


app = create_app()
