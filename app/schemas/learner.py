"""P3-03 learner, evidence, and state domain/API boundaries.

Strict Pydantic v2 schemas for the policy-independent learner-state concepts
defined in the Phase 3 graph. These schemas express the accepted P3-02 policy
and provenance requirements and contain no ORM, transaction, updater, planner,
or LLM behavior. The PracticeRecommendation decision contract is owned by
P3-08 and is intentionally absent here.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    model_validator,
)

from app.learner.writing_policy import STATE_QUANTUM, STATE_ROUNDING, WRITING_SKILLS
from app.schemas.common import BandScore
from app.schemas.writing import EvaluationMetadata

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]

# Canonical Writing skill key. Exactly the four skills frozen by P3-02; any
# unknown key is rejected.
WritingSkillKey = Literal[
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
]

# Frozen policy-version values from P3-02. planner_version is owned by P3-08,
# so P3-03 only requires it to be a non-blank string.
SkillTaxonomyVersion = Literal["writing-core-v1"]
StatePolicyVersion = Literal["writing-state-ewma-v1"]

# Derived learner-state value: 0.00 through 9.00 at 0.01 precision. This is
# NOT the IELTS half-band BandScore contract.
DerivedStateBand = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("9"), multiple_of=Decimal("0.01")),
]

# Fields that must be identical across the four LearningEvidence records of a
# single logical evaluation so a complete set cannot mix unrelated sources.
_EVIDENCE_IDENTITY_FIELDS: Final[tuple[str, ...]] = (
    "learning_update_id",
    "learner_id",
    "writing_evaluation_id",
    "source_created_at",
    "source_attempt_id",
)


class LearnerSchema(BaseModel):
    """Strict base for Phase 3 learner-state boundaries."""

    model_config = ConfigDict(extra="forbid")


class LearnerCreate(LearnerSchema):
    """Validated input for creating a learner."""

    writing_target_band: BandScore


class Learner(LearnerSchema):
    """A minimal learning identity with a Writing target band."""

    id: int = Field(gt=0)
    writing_target_band: BandScore
    created_at: datetime
    updated_at: datetime


class LearningUpdate(LearnerSchema):
    """Provenance and idempotency anchor for one applied Writing evaluation."""

    id: int = Field(gt=0)
    learner_id: int = Field(gt=0)
    writing_evaluation_id: int = Field(gt=0)
    skill_taxonomy_version: SkillTaxonomyVersion
    state_policy_version: StatePolicyVersion
    # Value is frozen by P3-08; P3-03 only requires it to be non-blank.
    planner_version: NonBlankText
    created_at: datetime


class LearningEvidence(LearnerSchema):
    """An immutable, append-only canonical criterion observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int = Field(gt=0)
    learning_update_id: int = Field(gt=0)
    learner_id: int = Field(gt=0)
    writing_evaluation_id: int = Field(gt=0)
    skill: WritingSkillKey
    observed_band: BandScore
    # Immutable canonical-order source values copied from WritingAttempt so
    # replay never depends on request-processing history.
    source_created_at: datetime
    source_attempt_id: int = Field(gt=0)
    provenance: EvaluationMetadata
    created_at: datetime


class LearnerSkillState(LearnerSchema):
    """The current materialized estimate for one learner and skill."""

    learner_id: int = Field(gt=0)
    skill: WritingSkillKey
    estimated_band: DerivedStateBand | None
    evidence_count: int = Field(ge=0)
    last_evidence_id: int | None = Field(default=None, gt=0)
    state_policy_version: StatePolicyVersion
    revision: int = Field(ge=0)
    updated_at: datetime

    @model_validator(mode="after")
    def _check_observed_consistency(self) -> "LearnerSkillState":
        if self.evidence_count == 0:
            if self.estimated_band is not None:
                raise ValueError("UNOBSERVED state must not set estimated_band")
            if self.last_evidence_id is not None:
                raise ValueError("UNOBSERVED state must not set last_evidence_id")
            if self.revision != 0:
                raise ValueError("UNOBSERVED state must have revision 0")
        else:
            if self.estimated_band is None:
                raise ValueError("observed state must set estimated_band")
            if self.last_evidence_id is None:
                raise ValueError("observed state must set last_evidence_id")
            if self.revision < 1:
                raise ValueError("observed state must have revision >= 1")
        return self

    @field_serializer("estimated_band", when_used="json")
    def _serialize_estimated_band(self, value: Decimal | None) -> str | None:
        """Serialize the derived band as a two-decimal string, never a float.

        P3-02 freezes materialized precision at two decimal places. The Python
        value remains a Decimal; only JSON output is normalized to exactly two
        decimal places using the frozen state quantum and rounding.
        """

        if value is None:
            return None
        return str(value.quantize(STATE_QUANTUM, rounding=STATE_ROUNDING))


class LearningEvidenceSet(LearnerSchema):
    """Exactly four canonical evidence records, keyed by skill.

    All four records must describe the same logical evaluation: they must share
    the same learning update, learner, evaluation, canonical-order source
    values, and Phase 2 provenance. Inconsistent input is rejected, never
    normalized.
    """

    task_response: LearningEvidence
    coherence_and_cohesion: LearningEvidence
    lexical_resource: LearningEvidence
    grammatical_range_and_accuracy: LearningEvidence

    @model_validator(mode="after")
    def _check_consistency(self) -> "LearningEvidenceSet":
        for skill in WRITING_SKILLS:
            item = getattr(self, skill)
            if item.skill != skill:
                raise ValueError(f"evidence under {skill!r} has skill {item.skill!r}")

        first = getattr(self, WRITING_SKILLS[0])
        for skill in WRITING_SKILLS:
            item = getattr(self, skill)
            for field in _EVIDENCE_IDENTITY_FIELDS:
                if getattr(item, field) != getattr(first, field):
                    raise ValueError(
                        f"evidence under {skill!r} has mismatched {field}"
                    )
            if item.provenance != first.provenance:
                raise ValueError(f"evidence under {skill!r} has mismatched provenance")
        return self


class LearnerSkillStateSet(LearnerSchema):
    """Exactly four materialized skill states, keyed by skill.

    All four states must belong to the same learner and the same state-policy
    version. Inconsistent input is rejected, never normalized.
    """

    task_response: LearnerSkillState
    coherence_and_cohesion: LearnerSkillState
    lexical_resource: LearnerSkillState
    grammatical_range_and_accuracy: LearnerSkillState

    @model_validator(mode="after")
    def _check_consistency(self) -> "LearnerSkillStateSet":
        for skill in WRITING_SKILLS:
            item = getattr(self, skill)
            if item.skill != skill:
                raise ValueError(f"state under {skill!r} has skill {item.skill!r}")

        first = getattr(self, WRITING_SKILLS[0])
        for skill in WRITING_SKILLS:
            item = getattr(self, skill)
            if item.learner_id != first.learner_id:
                raise ValueError(f"state under {skill!r} has mismatched learner_id")
            if item.state_policy_version != first.state_policy_version:
                raise ValueError(
                    f"state under {skill!r} has mismatched state_policy_version"
                )
        return self
