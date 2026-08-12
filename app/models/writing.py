"""SQLAlchemy persistence models for Writing Task 2 evaluations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _band_check(column: str) -> str:
    """Return the PostgreSQL check for a 0–9 half-band value."""

    return (
        f"{column} >= 0 AND {column} <= 9 "
        f"AND {column} * 2 = floor({column} * 2)"
    )


class WritingAttempt(Base):
    """A learner's immutable Task 2 question and essay submission."""

    __tablename__ = "writing_attempts"
    __table_args__ = (
        CheckConstraint(
            "length(trim(question)) > 0",
            name="ck_writing_attempt_question_nonblank",
        ),
        CheckConstraint(
            "length(trim(essay)) > 0",
            name="ck_writing_attempt_essay_nonblank",
        ),
        CheckConstraint(
            "word_count > 0",
            name="ck_writing_attempt_word_count_positive",
        ),
        Index("ix_writing_attempt_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    essay: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    evaluation: Mapped[WritingEvaluation | None] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
        uselist=False,
    )


class WritingEvaluation(Base):
    """One validated structured evaluation owned by a writing attempt."""

    __tablename__ = "writing_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            name="uq_writing_evaluation_attempt_id",
        ),
        CheckConstraint(
            _band_check("task_response_band"),
            name="ck_writing_evaluation_task_response_band",
        ),
        CheckConstraint(
            _band_check("coherence_and_cohesion_band"),
            name="ck_writing_evaluation_coherence_and_cohesion_band",
        ),
        CheckConstraint(
            _band_check("lexical_resource_band"),
            name="ck_writing_evaluation_lexical_resource_band",
        ),
        CheckConstraint(
            _band_check("grammatical_range_and_accuracy_band"),
            name="ck_writing_evaluation_grammatical_range_and_accuracy_band",
        ),
        CheckConstraint(
            _band_check("product_band"),
            name="ck_writing_evaluation_product_band",
        ),
        CheckConstraint(
            "length(trim(feedback)) > 0",
            name="ck_writing_evaluation_feedback_nonblank",
        ),
        CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_writing_evaluation_provider_nonblank",
        ),
        CheckConstraint(
            "length(trim(model)) > 0",
            name="ck_writing_evaluation_model_nonblank",
        ),
        CheckConstraint(
            "length(trim(prompt_version)) > 0",
            name="ck_writing_evaluation_prompt_version_nonblank",
        ),
        Index("ix_writing_evaluation_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "writing_attempts.id",
            name="fk_writing_evaluation_attempt_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    task_response_band: Mapped[Decimal] = mapped_column(
        Numeric(2, 1),
        nullable=False,
    )
    coherence_and_cohesion_band: Mapped[Decimal] = mapped_column(
        Numeric(2, 1),
        nullable=False,
    )
    lexical_resource_band: Mapped[Decimal] = mapped_column(
        Numeric(2, 1),
        nullable=False,
    )
    grammatical_range_and_accuracy_band: Mapped[Decimal] = mapped_column(
        Numeric(2, 1),
        nullable=False,
    )
    product_band: Mapped[Decimal] = mapped_column(
        Numeric(2, 1),
        nullable=False,
    )
    criteria_feedback: Mapped[dict[str, dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    error_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    recommended_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    attempt: Mapped[WritingAttempt] = relationship(back_populates="evaluation")
