"""Thin learner and learning API routes (P3-11).

Routes delegate all policy and transaction work to the application service and
the persistence layer. No business rules live here; every successful apply
response exposes exactly one auditable planning decision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.learner.writing_policy import WRITING_SKILLS, WRITING_STATE_POLICY_VERSION
from app.models.learning import (
    Learner as LearnerModel,
    LearnerSkillState as LearnerSkillStateModel,
)
from app.schemas.learner import (
    Learner,
    LearnerCreate,
    LearnerSkillState as LearnerSkillStateSchema,
    LearnerSkillStateSet,
)
from app.schemas.learning_api import (
    LearnerStateResponse,
    LearningApplyResponse,
)
from app.services.learning_application import (
    LearnerNotFoundError,
    apply_writing_evaluation,
)

router = APIRouter(prefix="/learners", tags=["learners"])


@router.post(
    "",
    response_model=Learner,
    status_code=status.HTTP_201_CREATED,
)
def create_learner(
    payload: LearnerCreate,
    session: Session = Depends(get_db_session),
) -> Learner:
    """Create a learner with a Writing target band."""
    row = LearnerModel(writing_target_band=payload.writing_target_band.value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return Learner(
        id=row.id,
        writing_target_band=payload.writing_target_band,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/{learner_id}/state", response_model=LearnerStateResponse)
def get_learner_state(
    learner_id: int,
    session: Session = Depends(get_db_session),
) -> LearnerStateResponse:
    """Return the four-skill materialized state for one learner.

    A learner with no accepted evidence yet is reported as a fully UNOBSERVED
    state set (evidence_count 0, null estimates, revision 0).
    """
    learner = session.get(LearnerModel, learner_id)
    if learner is None:
        raise LearnerNotFoundError(f"learner {learner_id} not found")

    rows = {
        row.skill: row
        for row in session.scalars(
            select(LearnerSkillStateModel).where(
                LearnerSkillStateModel.learner_id == learner_id
            )
        ).all()
    }
    states: dict[str, LearnerSkillStateSchema] = {}
    for skill in WRITING_SKILLS:
        row = rows.get(skill)
        if row is None:
            states[skill] = LearnerSkillStateSchema(
                learner_id=learner_id,
                skill=skill,
                estimated_band=None,
                evidence_count=0,
                last_evidence_id=None,
                state_policy_version=WRITING_STATE_POLICY_VERSION,
                revision=0,
                updated_at=learner.created_at,
            )
        else:
            states[skill] = LearnerSkillStateSchema(
                learner_id=row.learner_id,
                skill=row.skill,
                estimated_band=row.estimated_band,
                evidence_count=row.evidence_count,
                last_evidence_id=row.last_evidence_id,
                state_policy_version=row.state_policy_version,
                revision=row.revision,
                updated_at=row.updated_at,
            )
    return LearnerStateResponse(
        learner_id=learner_id,
        states=LearnerSkillStateSet(**states),
    )


@router.post(
    "/{learner_id}/writing/evaluations/{evaluation_id}/apply",
    response_model=LearningApplyResponse,
)
def apply_evaluation(
    learner_id: int,
    evaluation_id: int,
    session: Session = Depends(get_db_session),
) -> LearningApplyResponse:
    """Apply one persisted Writing evaluation to a learner atomically."""
    result = apply_writing_evaluation(
        session,
        learner_id=learner_id,
        writing_evaluation_id=evaluation_id,
    )
    return LearningApplyResponse(
        learning_update_id=result.learning_update_id,
        reused=result.reused,
        recommendation=result.recommendation,
    )
