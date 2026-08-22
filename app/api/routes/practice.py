"""Thin, separate Phase 4 Writing practice lifecycle routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import get_db_session
from app.llm.practice_generator import PracticeGenerator
from app.llm.provider import LLMProvider
from app.models.practice import WritingPractice
from app.schemas.knowledge import WritingGroundedGuidanceResponse
from app.schemas.practice import (
    ClosedLoopResult,
    GenerationOutcome,
    PracticeLifecycleState,
    PracticeResponse,
    PracticeSubmission,
    SubmissionResult,
)
from app.services.practice_completion import PracticeCompletionService
from app.services.practice_evaluation import PracticeEvaluationRetrievalService
from app.services.practice_generation import PracticeGenerationService
from app.services.practice_submission import PracticeSubmissionService
from app.services.writing_evaluation import WritingEvaluationService
from app.services.writing_guidance import WritingGuidanceService
from app.schemas.writing import WritingEvaluationResponse


router = APIRouter(prefix="/learners/{learner_id}/writing", tags=["practice"])


def _response(row: WritingPractice) -> PracticeResponse:
    return PracticeResponse(
        id=row.id,
        learner_id=row.learner_id,
        recommendation_id=row.recommendation_id,
        target_skill=row.target_skill,
        question=row.question,
        focus_objective=row.focus_objective,
        instructions=list(row.instructions),
        checkpoints=list(row.checkpoints),
        practice_type=row.practice_type,
        generator_policy_version=row.generator_policy_version,
        provider=row.provider,
        model=row.model,
        prompt_version=row.prompt_version,
        thinking_mode=row.thinking_mode,
        lifecycle_state=PracticeLifecycleState(row.lifecycle_state),
        attempt_id=row.attempt_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/guidance", response_model=WritingGroundedGuidanceResponse)
def get_writing_guidance(
    learner_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> WritingGroundedGuidanceResponse:
    """Return provider-free guidance from accepted learner chronology."""
    return WritingGuidanceService(session).get(learner_id=learner_id)


@router.post(
    "/recommendations/{recommendation_id}/practice", response_model=GenerationOutcome
)
async def generate_practice(
    learner_id: int,
    recommendation_id: int,
    generator: Annotated[PracticeGenerator, Depends(get_practice_generator)],
    session: Annotated[Session, Depends(get_db_session)],
) -> GenerationOutcome:
    return await PracticeGenerationService(session, generator).generate_or_resolve(
        learner_id=learner_id, recommendation_id=recommendation_id
    )


@router.get("/practices/{practice_id}", response_model=PracticeResponse)
def inspect_practice(
    learner_id: int,
    practice_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> PracticeResponse:
    row = session.scalar(
        select(WritingPractice).where(
            WritingPractice.id == practice_id, WritingPractice.learner_id == learner_id
        )
    )
    if row is None:
        from app.services.practice_completion import PracticeCompletionNotFoundError

        raise PracticeCompletionNotFoundError("writing practice was not found")
    return _response(row)


@router.get(
    "/practices/{practice_id}/evaluation", response_model=WritingEvaluationResponse
)
def get_practice_evaluation(
    learner_id: int,
    practice_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> WritingEvaluationResponse:
    return PracticeEvaluationRetrievalService(session).get(
        learner_id=learner_id, practice_id=practice_id
    )


@router.post("/practices/{practice_id}/submit", response_model=SubmissionResult)
async def submit_practice(
    learner_id: int,
    practice_id: int,
    payload: PracticeSubmission,
    provider: Annotated[LLMProvider, Depends(get_writing_provider)],
    session: Annotated[Session, Depends(get_db_session)],
) -> SubmissionResult:
    return await PracticeSubmissionService(
        session, WritingEvaluationService(provider)
    ).submit(learner_id=learner_id, practice_id=practice_id, submission=payload)


@router.post("/practices/{practice_id}/complete", response_model=ClosedLoopResult)
def complete_practice(
    learner_id: int,
    practice_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ClosedLoopResult:
    return PracticeCompletionService(session).complete(
        learner_id=learner_id, practice_id=practice_id
    )
