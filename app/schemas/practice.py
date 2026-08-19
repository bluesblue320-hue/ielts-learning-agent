"""P4-04 Phase 4 practice domain and API schemas.

These schemas freeze the practice product contract
(`writing-practice-product-v1`) and the generation policy
(`writing-practice-generation-v1`) at the Pydantic v2 boundary. They are
domain/API boundaries only: no ORM, database, provider, or service behavior
lives here.

Phase 4 `PracticeSubmission` is deliberately NOT the Phase 2
`WritingSubmission`: it carries the essay only. The trusted question comes
from the persisted practice; the service composes the existing Phase 2
`WritingSubmission` internally.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.learner import WritingSkillKey
from app.schemas.planning import AnyPracticeRecommendationDecision
from app.schemas.writing import WritingEssayText

# Frozen generation-policy maximum sizes (writing-practice-generation-v1).
MAX_PRACTICE_QUESTION_CHARACTERS = 400
MAX_PRACTICE_OBJECTIVE_CHARACTERS = 300
MAX_PRACTICE_ITEM_CHARACTERS = 200
MIN_PRACTICE_ITEMS = 1
MAX_PRACTICE_ITEMS = 6


class PracticeSchema(BaseModel):
    """Strict immutable base for Phase 4 practice boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


PracticeQuestionText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_PRACTICE_QUESTION_CHARACTERS,
    ),
]
PracticeObjectiveText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_PRACTICE_OBJECTIVE_CHARACTERS,
    ),
]
PracticeItemText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_PRACTICE_ITEM_CHARACTERS,
    ),
]
PracticeItemList = Annotated[
    list[PracticeItemText],
    Field(min_length=MIN_PRACTICE_ITEMS, max_length=MAX_PRACTICE_ITEMS),
]


class PracticeLifecycleState(StrEnum):
    """Frozen submission lifecycle around the durable practice."""

    GENERATED = "generated"
    SUBMISSION_IN_PROGRESS = "submission_in_progress"
    SUBMITTED = "submitted"


class PracticeSubmission(PracticeSchema):
    """Phase 4 submission input: essay only.

    The question is NOT part of the submission; it is authoritative from the
    persisted practice and can never be replaced by the client.
    """

    essay: WritingEssayText


class GeneratedWritingPractice(PracticeSchema):
    """Validated structured generator output (authority-mirroring enforced).

    ``target_skill`` mirrors the persisted recommendation's target skill and
    MUST equal it; a mismatch is an invalid provider response.
    """

    practice_type: str = Field(min_length=1, max_length=64)
    target_skill: WritingSkillKey
    question: PracticeQuestionText
    focus_objective: PracticeObjectiveText
    instructions: PracticeItemList
    checkpoints: PracticeItemList
    generator_policy_version: Literal["writing-practice-generation-v1"]
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=64)
    prompt_version: str = Field(min_length=1, max_length=64)
    thinking_mode: Literal["enabled", "disabled"]


class PracticeResponse(PracticeSchema):
    """One persisted practice as exposed by the API."""

    id: int = Field(gt=0)
    learner_id: int = Field(gt=0)
    recommendation_id: int = Field(gt=0)
    target_skill: WritingSkillKey
    question: PracticeQuestionText
    focus_objective: PracticeObjectiveText
    instructions: list[str]
    checkpoints: list[str]
    practice_type: str
    generator_policy_version: str
    provider: str
    model: str
    prompt_version: str
    thinking_mode: str
    lifecycle_state: PracticeLifecycleState
    attempt_id: int | None = None
    created_at: datetime
    updated_at: datetime


class GenerationOutcome(PracticeSchema):
    """Result of a generate/resolve call.

    A `practice` decision yields exactly one persisted practice. A
    `no_practice` decision yields a deterministic no-practice outcome with the
    Phase 3-owned reason codes and NO practice row.
    """

    decision: Literal["practice", "no_practice"]
    practice: PracticeResponse | None = None
    no_practice_reasons: list[str] = Field(default_factory=list)


class SubmissionResult(PracticeSchema):
    """Result of a submission call.

    ``status`` distinguishes the deterministic outcomes: ``submitted`` (new
    finalization), ``reused`` (same-fingerprint retry returning the existing
    result), ``conflict`` (different fingerprint), and ``in_progress``
    (another claim is active).
    """

    status: Literal["submitted", "reused", "conflict", "in_progress"]
    attempt_id: int | None = None
    evaluation_id: int | None = None


class ClosedLoopResult(PracticeSchema):
    """Closed-loop completion & replan result.

    The authoritative trace: practice -> attempt -> evaluation ->
    LearningUpdate -> next PracticeRecommendation. The next recommendation may
    be `practice` or `no_practice`; both are valid successful outcomes.
    """

    practice_id: int = Field(gt=0)
    attempt_id: int = Field(gt=0)
    evaluation_id: int = Field(gt=0)
    learning_update_id: int = Field(gt=0)
    next_recommendation_id: int = Field(gt=0)
    next_recommendation: AnyPracticeRecommendationDecision
