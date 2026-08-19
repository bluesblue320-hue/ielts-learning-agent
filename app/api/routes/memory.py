"""Thin Phase 6 memory read routes (P6-08).

Four frozen read endpoints. Routes remain thin: learner existence is checked,
then the read-model services project persisted rows. No provider call and no
mutation is possible on these routes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.memory.context import build_learner_context
from app.memory.episode_queries import get_learner_episode, list_learner_episodes
from app.memory.profile import build_learner_progress
from app.models.learning import Learner
from app.schemas.memory import (
    LearningEpisodeDetail,
    WritingContextResponse,
    WritingHistoryResponse,
    WritingProgressResponse,
)
from app.services.learning_application import LearnerNotFoundError

router = APIRouter(prefix="/learners/{learner_id}/writing", tags=["memory"])


def _require_learner(session: Session, learner_id: int) -> None:
    if session.get(Learner, learner_id) is None:
        raise LearnerNotFoundError(f"learner {learner_id} not found")


@router.get("/history", response_model=WritingHistoryResponse)
def writing_history(
    learner_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> WritingHistoryResponse:
    """What did I do? Learner-owned L0 episodes in frozen order."""
    _require_learner(session, learner_id)
    episodes = list_learner_episodes(session, learner_id=learner_id)
    return WritingHistoryResponse(learner_id=learner_id, episodes=episodes)


@router.get("/history/{episode_id}", response_model=LearningEpisodeDetail)
def writing_history_episode(
    learner_id: int,
    episode_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> LearningEpisodeDetail:
    """What happened in that specific episode? Full L0 reconstruction."""
    _require_learner(session, learner_id)
    return get_learner_episode(
        session,
        learner_id=learner_id,
        episode_id=episode_id,
    )


@router.get("/progress", response_model=WritingProgressResponse)
def writing_progress(
    learner_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> WritingProgressResponse:
    """How have I changed? L2 patterns + L3 profile section."""
    return build_learner_progress(session, learner_id=learner_id)


@router.get("/context", response_model=WritingContextResponse)
def writing_context(
    learner_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> WritingContextResponse:
    """Where should I continue? Server-authoritative resume context."""
    return build_learner_context(session, learner_id=learner_id)
