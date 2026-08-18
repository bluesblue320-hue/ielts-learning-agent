"""Thin HTTP route for Writing Task 2 evaluation."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.writing import get_writing_provider
from app.db.session import get_db_session
from app.llm.provider import LLMProvider
from app.schemas.errors import APIErrorResponse
from app.schemas.writing import (
    WritingEvaluationResponse,
    WritingSubmission,
)
from app.services.writing_evaluation import WritingEvaluationService
from app.services.writing_persistence import WritingEvaluationPersistenceService


router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/evaluate",
    response_model=WritingEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": APIErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": APIErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": APIErrorResponse},
        status.HTTP_504_GATEWAY_TIMEOUT: {"model": APIErrorResponse},
    },
)
async def evaluate_writing(
    submission: WritingSubmission,
    provider: Annotated[LLMProvider, Depends(get_writing_provider)],
    session: Annotated[Session, Depends(get_db_session)],
) -> WritingEvaluationResponse:
    """Evaluate and atomically persist one validated Task 2 submission."""

    evaluation = await WritingEvaluationService(provider).evaluate(submission)
    persisted = WritingEvaluationPersistenceService(session).persist(
        submission,
        evaluation,
    )

    return WritingEvaluationResponse(
        attempt_id=persisted.attempt_id,
        evaluation_id=persisted.evaluation_id,
        evaluation=evaluation,
    )
