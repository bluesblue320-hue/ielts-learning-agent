"""Thin Phase 8 Core Learning Agent turn route."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.executor import AgentTurnExecutor
from app.agent.observation import observe_agent_state
from app.agent.tools import AgentTools
from app.api.dependencies.agent import (
    get_agent_generator_factory,
    get_agent_provider_factory,
)
from app.db.session import get_db_session
from app.schemas.agent import AgentTurn, AgentTurnResponse

router = APIRouter(prefix="/learners/{learner_id}/writing/agent", tags=["agent"])


@router.post("/turn", response_model=AgentTurnResponse)
async def agent_turn(
    learner_id: int,
    payload: AgentTurn,
    session: Annotated[Session, Depends(get_db_session)],
    generator_factory: Annotated[Callable[[], object], Depends(get_agent_generator_factory)],
    provider_factory: Annotated[Callable[[], object], Depends(get_agent_provider_factory)],
) -> AgentTurnResponse:
    """Run one explicit bounded turn; factories resolve only when a tool needs them."""

    tools = AgentTools(
        session=session,
        generator_factory=generator_factory,
        provider_factory=provider_factory,
    )
    executor = AgentTurnExecutor(
        tools=tools,
        observe=lambda current_learner_id: observe_agent_state(
            session,
            learner_id=current_learner_id,
        ),
    )
    return await executor.execute(learner_id=learner_id, turn=payload)