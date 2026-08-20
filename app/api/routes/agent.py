"""Thin Phase 8 Core Learning Agent turn route."""
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.agent.executor import AgentTurnExecutor
from app.agent.observation import observe_agent_state
from app.agent.tools import AgentTools
from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import get_db_session
from app.schemas.agent import AgentTurn, AgentTurnResponse

router = APIRouter(prefix="/learners/{learner_id}/agent", tags=["agent"])

@router.post("/turn", response_model=AgentTurnResponse)
async def agent_turn(learner_id: int, payload: AgentTurn, session: Annotated[Session, Depends(get_db_session)]) -> AgentTurnResponse:
    """Run one explicit bounded turn; dependencies are lazy behind tools."""
    tools = AgentTools(session=session, generator_factory=get_practice_generator, provider_factory=get_writing_provider)
    executor = AgentTurnExecutor(tools=tools, observe=lambda current_learner_id: observe_agent_state(session, learner_id=current_learner_id))
    return await executor.execute(learner_id=learner_id, turn=payload)
