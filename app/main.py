"""FastAPI application entry point."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build the Phase 1 API application without external side effects."""
    return FastAPI(title="IELTS Learning Agent", version="0.1.0")


app = create_app()
