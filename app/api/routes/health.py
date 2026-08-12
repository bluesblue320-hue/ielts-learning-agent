"""Liveness and readiness API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.services.health import database_is_available


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Report process liveness without accessing external services."""
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(
    session: Annotated[Session, Depends(get_db_session)],
) -> ReadinessResponse | JSONResponse:
    """Report database-backed application readiness."""
    available = database_is_available(session)
    response = ReadinessResponse(
        status="ready" if available else "not_ready",
        database="available" if available else "unavailable",
    )
    if not available:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(),
        )
    return response
