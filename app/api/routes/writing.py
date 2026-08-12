"""Thin HTTP route for Writing Task 2 evaluation."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.writing import get_writing_provider
from app.db.session import get_db_session
from app.llm.provider import LLMProvider, ProviderError
from app.schemas.writing import (
    WritingEvaluationResponse,
    WritingSubmission,
)
from app.services.writing_evaluation import WritingEvaluationService
from app.services.writing_persistence import (
    WritingEvaluationPersistenceService,
    WritingPersistenceError,
)


router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/evaluate",
    response_model=WritingEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_writing(
    submission: WritingSubmission,
    provider: Annotated[LLMProvider, Depends(get_writing_provider)],
    session: Annotated[Session, Depends(get_db_session)],
) -> WritingEvaluationResponse:
    """Evaluate and atomically persist one validated Task 2 submission."""

    try:
        evaluation = await WritingEvaluationService(provider).evaluate(submission)
        persisted = WritingEvaluationPersistenceService(session).persist(
            submission,
            evaluation,
        )
    except ProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Writing evaluation provider failed.",
        ) from None
    except WritingPersistenceError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Writing evaluation could not be persisted.",
        ) from None

    return WritingEvaluationResponse(
        attempt_id=persisted.attempt_id,
        evaluation=evaluation,
    )
