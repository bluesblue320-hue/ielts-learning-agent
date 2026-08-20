"""SQLAlchemy 2.x persistence model for Phase 4 Writing practice.

This model encodes the accepted Phase 4 product contract and generation
policy at the database layer. It is persistence structure only: no
generation, claim, evaluation, or service behavior lives here. Migration
creation is owned by P4-06.

Ownership is database-enforced: ``writing_practices(recommendation_id,
learner_id)`` references ``practice_recommendations(id, learner_id)`` through
a composite FK (RESTRICT), so a practice can never claim a recommendation
from one learner while storing another learner's id. ``UNIQUE
(recommendation_id)`` additionally enforces at most one durable practice per
eligible recommendation. Deletion semantics are protective (RESTRICT) so the
auditable practice -> attempt -> evaluation -> learning-update chain never
silently disappears.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WritingPractice(Base):
    """One durable targeted Writing Task 2 practice for one learner."""

    __tablename__ = "writing_practices"
    __table_args__ = (
        # At most one durable practice per eligible practice recommendation.
        UniqueConstraint(
            "recommendation_id",
            name="uq_writing_practice_recommendation_id",
        ),
        # One attempt can belong to at most one practice; multiple NULLs are
        # allowed before submission (PostgreSQL NULLS DISTINCT default).
        UniqueConstraint("attempt_id", name="uq_writing_practice_attempt_id"),
        # Database-enforced ownership: the recommendation must belong to the
        # same learner as the practice row.
        ForeignKeyConstraint(
            ["recommendation_id", "learner_id"],
            ["practice_recommendations.id", "practice_recommendations.learner_id"],
            name="fk_writing_practice_recommendation_ownership",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "lifecycle_state IN ('generated', 'submission_in_progress', 'submitted')",
            name="ck_writing_practice_lifecycle_state",
        ),
        CheckConstraint(
            "length(trim(question)) > 0 AND length(question) <= 400",
            name="ck_writing_practice_question_length",
        ),
        CheckConstraint(
            "length(trim(focus_objective)) > 0 AND length(focus_objective) <= 300",
            name="ck_writing_practice_objective_length",
        ),
        CheckConstraint(
            "jsonb_typeof(instructions) = 'array'",
            name="ck_writing_practice_instructions_array",
        ),
        CheckConstraint(
            "jsonb_typeof(checkpoints) = 'array'",
            name="ck_writing_practice_checkpoints_array",
        ),
        CheckConstraint(
            "length(trim(generator_policy_version)) > 0",
            name="ck_writing_practice_generator_policy_version_nonblank",
        ),
        CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_writing_practice_provider_nonblank",
        ),
        CheckConstraint(
            "length(trim(model)) > 0",
            name="ck_writing_practice_model_nonblank",
        ),
        CheckConstraint(
            "length(trim(prompt_version)) > 0",
            name="ck_writing_practice_prompt_version_nonblank",
        ),
        CheckConstraint(
            "thinking_mode IN ('enabled', 'disabled')",
            name="ck_writing_practice_thinking_mode",
        ),
        # Generated content exists only for successful generation; a submitted
        # practice must carry its attempt link.
        CheckConstraint(
            "(lifecycle_state = 'submitted' AND attempt_id IS NOT NULL)"
            " OR (lifecycle_state IN ('generated', 'submission_in_progress')"
            " AND attempt_id IS NULL)",
            name="ck_writing_practice_attempt_nullability",
        ),
        # The submission claim is a durable lease. Each lifecycle state has
        # one exact metadata shape so partial claims cannot become valid data.
        CheckConstraint(
            "(lifecycle_state = 'generated'"
            " AND submission_fingerprint IS NULL"
            " AND claim_token IS NULL"
            " AND submission_claimed_at IS NULL"
            " AND attempt_id IS NULL)"
            " OR (lifecycle_state = 'submission_in_progress'"
            " AND submission_fingerprint IS NOT NULL"
            " AND claim_token IS NOT NULL"
            " AND submission_claimed_at IS NOT NULL"
            " AND attempt_id IS NULL)"
            " OR (lifecycle_state = 'submitted'"
            " AND submission_fingerprint IS NOT NULL"
            " AND claim_token IS NULL"
            " AND submission_claimed_at IS NULL"
            " AND attempt_id IS NOT NULL)",
            name="ck_writing_practice_submission_state_matrix",
        ),
        Index(
            "ix_writing_practice_learner_state",
            "learner_id",
            "lifecycle_state",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    learner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learners.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recommendation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_skill: Mapped[str] = mapped_column(String(64), nullable=False)
    practice_type: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(String(400), nullable=False)
    focus_objective: Mapped[str] = mapped_column(String(300), nullable=False)
    instructions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    checkpoints: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    generator_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    thinking_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)
    submission_fingerprint: Mapped[str | None] = mapped_column(String(128))
    claim_token: Mapped[str | None] = mapped_column(String(128))
    submission_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    attempt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("writing_attempts.id", ondelete="RESTRICT"),
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
