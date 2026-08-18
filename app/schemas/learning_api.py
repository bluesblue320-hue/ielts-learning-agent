"""P3-11 learner and learning API response boundaries.

These are thin response schemas for the learner routes. Business rules live in
the application service; routes only map request/response and error codes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.learner import LearnerSkillStateSet
from app.schemas.planning import PracticeRecommendationDecision


class LearningApiSchema(BaseModel):
    """Strict base for learner API boundaries."""

    model_config = ConfigDict(extra="forbid")


class LearnerStateResponse(LearningApiSchema):
    """The four-skill materialized state for one learner."""

    learner_id: int = Field(gt=0)
    states: LearnerSkillStateSet


class LearningApplyResponse(LearningApiSchema):
    """The auditable outcome of applying one evaluation to a learner.

    ``reused`` is true when the request was an idempotent replay of an already
    applied evaluation. The recommendation exposes the persisted ``practice``
    or ``no_practice`` planning decision.
    """

    learning_update_id: int = Field(gt=0)
    reused: bool
    recommendation_id: int = Field(gt=0)
    recommendation: PracticeRecommendationDecision
