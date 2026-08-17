"""SQLAlchemy 2.x persistence models for Phase 3 learner-state concepts.

These models encode the accepted P3-02, P3-03, and P3-08 contracts at the
database-model layer. They are persistence structure only: no extraction,
state-update, planner, service, API, or LLM behavior lives here. Migration
creation is owned by P3-05.

Deletion semantics are protective: Phase 2 source references and learner-owned
Phase 3 history use RESTRICT so applied evaluation history never silently
disappears.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.writing import WritingAttempt, WritingEvaluation

_CANONICAL_SKILLS: tuple[str, ...] = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)

_PRACTICE_REASON_SEQUENCES: tuple[str, ...] = (
    '["largest_target_gap"]',
    '["largest_target_gap","priority_tiebreak"]',
    '["largest_target_gap","insufficient_evidence"]',
    '["largest_target_gap","priority_tiebreak","insufficient_evidence"]',
)

_NO_PRACTICE_REASON_SEQUENCES: tuple[str, ...] = (
    '["target_achieved"]',
    '["target_achieved","insufficient_evidence"]',
    '["cold_start"]',
    '["incomplete_state"]',
    '["target_unset"]',
)


def _half_band_check(column: str) -> str:
    """Return the PostgreSQL check for a 0-9 half-band value."""

    return (
        f"{column} >= 0 AND {column} <= 9 "
        f"AND {column} * 2 = floor({column} * 2)"
    )


def _canonical_skill_check(column: str) -> str:
    """Return the PostgreSQL check allowing only the four canonical skills."""

    values = ", ".join(repr(skill) for skill in _CANONICAL_SKILLS)
    return f"{column} IN ({values})"


def _jsonb_array_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'::jsonb" for value in values)


def _reason_sequences_check(column: str) -> str:
    all_sequences = _PRACTICE_REASON_SEQUENCES + _NO_PRACTICE_REASON_SEQUENCES
    return f"{column} IN ({_jsonb_array_values(all_sequences)})"


def _practice_sequences_check(column: str) -> str:
    return f"{column} IN ({_jsonb_array_values(_PRACTICE_REASON_SEQUENCES)})"


def _no_practice_sequences_check(column: str) -> str:
    return f"{column} IN ({_jsonb_array_values(_NO_PRACTICE_REASON_SEQUENCES)})"


class Learner(Base):
    """A minimal learning identity with an IELTS Writing target band."""

    __tablename__ = "learners"
    __table_args__ = (
        CheckConstraint(
            _half_band_check("writing_target_band"),
            name="ck_learner_writing_target_band",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    writing_target_band: Mapped[Decimal] = mapped_column(
        Numeric(2, 1),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    learning_updates: Mapped[list[LearningUpdate]] = relationship(
        back_populates="learner",
        passive_deletes=True,
    )
    skill_states: Mapped[list[LearnerSkillState]] = relationship(
        back_populates="learner",
        passive_deletes=True,
    )
    recommendations: Mapped[list[PracticeRecommendation]] = relationship(
        back_populates="learner",
        passive_deletes=True,
    )


class LearningUpdate(Base):
    """Provenance and idempotency anchor for one applied Writing evaluation."""

    __tablename__ = "learning_updates"
    __table_args__ = (
        # Two-column candidate key backing the PracticeRecommendation composite
        # ownership FK (learning_update_id, learner_id) -> (id, learner_id).
        UniqueConstraint(
            "id",
            "learner_id",
            name="uq_learning_update_learner_identity",
        ),
        # The composite candidate key that evidence uses as its ownership
        # target.
        UniqueConstraint(
            "id",
            "learner_id",
            "writing_evaluation_id",
            name="uq_learning_update_identity",
        ),
        CheckConstraint(
            "length(trim(skill_taxonomy_version)) > 0",
            name="ck_learning_update_skill_taxonomy_version_nonblank",
        ),
        CheckConstraint(
            "length(trim(state_policy_version)) > 0",
            name="ck_learning_update_state_policy_version_nonblank",
        ),
        CheckConstraint(
            "length(trim(planner_version)) > 0",
            name="ck_learning_update_planner_version_nonblank",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learners.id", name="fk_learning_update_learner_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Globally unique: one persisted WritingEvaluation has at most one owner.
    writing_evaluation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "writing_evaluations.id",
            name="fk_learning_update_writing_evaluation_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
    )
    skill_taxonomy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    planner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    learner: Mapped[Learner] = relationship(back_populates="learning_updates")
    writing_evaluation: Mapped[WritingEvaluation] = relationship()
    evidence: Mapped[list[LearningEvidence]] = relationship(
        back_populates="learning_update",
        passive_deletes=True,
    )
    recommendation: Mapped[PracticeRecommendation | None] = relationship(
        back_populates="learning_update",
        uselist=False,
        passive_deletes=True,
        primaryjoin="PracticeRecommendation.learning_update_id == LearningUpdate.id",
    )


class LearningEvidence(Base):
    """An immutable, append-only canonical criterion observation."""

    __tablename__ = "learning_evidence"
    __table_args__ = (
        # Composite ownership: an evidence row cannot claim an update of another
        # learner or another evaluation.
        ForeignKeyConstraint(
            ["learning_update_id", "learner_id", "writing_evaluation_id"],
            [
                "learning_updates.id",
                "learning_updates.learner_id",
                "learning_updates.writing_evaluation_id",
            ],
            name="fk_learning_evidence_learning_update_ownership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_attempt_id"],
            ["writing_attempts.id"],
            name="fk_learning_evidence_source_attempt_id",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "learning_update_id",
            "skill",
            name="uq_learning_evidence_update_skill",
        ),
        # Candidate key used by LearnerSkillState.last_evidence_id ownership.
        UniqueConstraint(
            "id",
            "learner_id",
            "skill",
            name="uq_learning_evidence_identity",
        ),
        CheckConstraint(
            _canonical_skill_check("skill"),
            name="ck_learning_evidence_skill",
        ),
        CheckConstraint(
            _half_band_check("observed_band"),
            name="ck_learning_evidence_observed_band",
        ),
        CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_learning_evidence_provider_nonblank",
        ),
        CheckConstraint(
            "length(trim(model)) > 0",
            name="ck_learning_evidence_model_nonblank",
        ),
        CheckConstraint(
            "length(trim(prompt_version)) > 0",
            name="ck_learning_evidence_prompt_version_nonblank",
        ),
        CheckConstraint(
            "length(trim(rubric_version)) > 0",
            name="ck_learning_evidence_rubric_version_nonblank",
        ),
        CheckConstraint(
            "length(trim(scoring_policy_version)) > 0",
            name="ck_learning_evidence_scoring_policy_version_nonblank",
        ),
        CheckConstraint(
            "thinking_mode IN ('enabled', 'disabled')",
            name="ck_learning_evidence_thinking_mode",
        ),
        # Canonical replay order: learner, skill, then WritingAttempt.created_at
        # ASC, WritingAttempt.id ASC. Evidence insertion chronology is never used.
        Index(
            "ix_learning_evidence_canonical_replay",
            "learner_id",
            "skill",
            "source_created_at",
            "source_attempt_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    learning_update_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    learner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    writing_evaluation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    skill: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_band: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    source_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    source_attempt_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scoring_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    thinking_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    learning_update: Mapped[LearningUpdate] = relationship(
        back_populates="evidence",
        foreign_keys=[learning_update_id, learner_id, writing_evaluation_id],
    )
    source_attempt: Mapped[WritingAttempt] = relationship(
        foreign_keys=[source_attempt_id],
    )


class LearnerSkillState(Base):
    """The current materialized estimate for one learner and skill."""

    __tablename__ = "learner_skill_states"
    __table_args__ = (
        CheckConstraint(
            _canonical_skill_check("skill"),
            name="ck_learner_skill_state_skill",
        ),
        CheckConstraint(
            "estimated_band >= 0 AND estimated_band <= 9",
            name="ck_learner_skill_state_estimated_band_range",
        ),
        CheckConstraint(
            "evidence_count >= 0",
            name="ck_learner_skill_state_evidence_count_nonnegative",
        ),
        CheckConstraint(
            "revision >= 0",
            name="ck_learner_skill_state_revision_nonnegative",
        ),
        CheckConstraint(
            "length(trim(state_policy_version)) > 0",
            name="ck_learner_skill_state_state_policy_version_nonblank",
        ),
        # Mirrors the accepted P3-03 observed/UNOBSERVED contract.
        CheckConstraint(
            "(evidence_count = 0 AND estimated_band IS NULL "
            "AND last_evidence_id IS NULL AND revision = 0)"
            " OR (evidence_count > 0 AND estimated_band IS NOT NULL "
            "AND last_evidence_id IS NOT NULL AND revision >= 1)",
            name="ck_learner_skill_state_observed_consistency",
        ),
        # last_evidence_id cannot point at evidence owned by another learner or
        # skill. NULL (UNOBSERVED) is skipped under MATCH SIMPLE.
        ForeignKeyConstraint(
            ["last_evidence_id", "learner_id", "skill"],
            [
                "learning_evidence.id",
                "learning_evidence.learner_id",
                "learning_evidence.skill",
            ],
            name="fk_learner_skill_state_last_evidence_ownership",
            ondelete="RESTRICT",
        ),
    )

    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learners.id", name="fk_learner_skill_state_learner_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    skill: Mapped[str] = mapped_column(String(64), primary_key=True)
    estimated_band: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    state_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    last_evidence_id: Mapped[int | None] = mapped_column(BigInteger)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    learner: Mapped[Learner] = relationship(back_populates="skill_states")


class PracticeRecommendation(Base):
    """The single persisted planning decision for one successful learning update."""

    __tablename__ = "practice_recommendations"
    __table_args__ = (
        # Phase 4 ownership candidate key: referenced by the
        # writing_practices(recommendation_id, learner_id) composite FK.
        UniqueConstraint(
            "id",
            "learner_id",
            name="uq_practice_recommendation_id_learner",
        ),
        # A recommendation belongs to the same learner as its LearningUpdate.
        ForeignKeyConstraint(
            ["learning_update_id", "learner_id"],
            ["learning_updates.id", "learning_updates.learner_id"],
            name="fk_practice_recommendation_learning_update_ownership",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "decision_type IN ('practice', 'no_practice')",
            name="ck_practice_recommendation_decision_type",
        ),
        CheckConstraint(
            f"target_skill IS NULL OR {_canonical_skill_check('target_skill')}",
            name="ck_practice_recommendation_target_skill",
        ),
        CheckConstraint(
            "learner_target_band IS NULL OR "
            + _half_band_check("learner_target_band"),
            name="ck_practice_recommendation_learner_target_band",
        ),
        CheckConstraint(
            "current_estimate IS NULL OR "
            "(current_estimate >= 0 AND current_estimate <= 9)",
            name="ck_practice_recommendation_current_estimate_range",
        ),
        CheckConstraint(
            "length(trim(planner_version)) > 0",
            name="ck_practice_recommendation_planner_version_nonblank",
        ),
        CheckConstraint(
            "jsonb_typeof(reason_codes) = 'array'",
            name="ck_practice_recommendation_reason_codes_array",
        ),
        CheckConstraint(
            "jsonb_typeof(state_snapshot) = 'object'",
            name="ck_practice_recommendation_state_snapshot_object",
        ),
        CheckConstraint(
            _reason_sequences_check("reason_codes"),
            name="ck_practice_recommendation_reason_sequences",
        ),
        CheckConstraint(
            "(decision_type = 'practice' AND "
            + _practice_sequences_check("reason_codes")
            + ") OR (decision_type = 'no_practice' AND "
            + _no_practice_sequences_check("reason_codes")
            + ")",
            name="ck_practice_recommendation_reason_decision",
        ),
        # target_unset must carry a null target; every other outcome requires it.
        CheckConstraint(
            "(reason_codes = '[\"target_unset\"]'::jsonb "
            "AND learner_target_band IS NULL)"
            " OR (reason_codes <> '[\"target_unset\"]'::jsonb "
            "AND learner_target_band IS NOT NULL)",
            name="ck_practice_recommendation_target_band_nullability",
        ),
        # practice / no_practice decision shape (P3-08 section 13/14).
        CheckConstraint(
            "(decision_type = 'practice' AND target_skill IS NOT NULL "
            "AND learner_target_band IS NOT NULL AND current_estimate IS NOT NULL)"
            " OR (decision_type = 'no_practice' AND target_skill IS NULL "
            "AND current_estimate IS NULL)",
            name="ck_practice_recommendation_decision_shape",
        ),
        CheckConstraint(
            "state_snapshot ? 'task_response'"
            " AND state_snapshot ? 'coherence_and_cohesion'"
            " AND state_snapshot ? 'lexical_resource'"
            " AND state_snapshot ? 'grammatical_range_and_accuracy'",
            name="ck_practice_recommendation_snapshot_skills",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    learning_update_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        unique=True,
    )
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learners.id", name="fk_practice_recommendation_learner_id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_skill: Mapped[str | None] = mapped_column(String(64))
    learner_target_band: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    current_estimate: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    planner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    learning_update: Mapped[LearningUpdate] = relationship(
        back_populates="recommendation",
        primaryjoin="PracticeRecommendation.learning_update_id == LearningUpdate.id",
    )
    learner: Mapped[Learner] = relationship(
        back_populates="recommendations",
        foreign_keys=[learner_id],
    )
