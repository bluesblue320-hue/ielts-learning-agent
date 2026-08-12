"""Add Writing Task 2 attempt and evaluation tables.

Revision ID: 0002_writing
Revises: 0001_phase1
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_writing"
down_revision: str | None = "0001_phase1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Phase 2 writing persistence schema."""

    op.create_table(
        "writing_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("essay", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(question)) > 0",
            name="ck_writing_attempt_question_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(essay)) > 0",
            name="ck_writing_attempt_essay_nonblank",
        ),
        sa.CheckConstraint(
            "word_count > 0",
            name="ck_writing_attempt_word_count_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_writing_attempt_created_at",
        "writing_attempts",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "writing_evaluations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.BigInteger(), nullable=False),
        sa.Column("task_response_band", sa.Numeric(2, 1), nullable=False),
        sa.Column(
            "coherence_and_cohesion_band",
            sa.Numeric(2, 1),
            nullable=False,
        ),
        sa.Column("lexical_resource_band", sa.Numeric(2, 1), nullable=False),
        sa.Column(
            "grammatical_range_and_accuracy_band",
            sa.Numeric(2, 1),
            nullable=False,
        ),
        sa.Column("product_band", sa.Numeric(2, 1), nullable=False),
        sa.Column("criteria_feedback", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("error_tags", sa.JSON(), nullable=False),
        sa.Column("recommended_skills", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "task_response_band >= 0 AND task_response_band <= 9 "
            "AND task_response_band * 2 = floor(task_response_band * 2)",
            name="ck_writing_evaluation_task_response_band",
        ),
        sa.CheckConstraint(
            "coherence_and_cohesion_band >= 0 "
            "AND coherence_and_cohesion_band <= 9 "
            "AND coherence_and_cohesion_band * 2 = "
            "floor(coherence_and_cohesion_band * 2)",
            name="ck_writing_evaluation_coherence_and_cohesion_band",
        ),
        sa.CheckConstraint(
            "lexical_resource_band >= 0 AND lexical_resource_band <= 9 "
            "AND lexical_resource_band * 2 = floor(lexical_resource_band * 2)",
            name="ck_writing_evaluation_lexical_resource_band",
        ),
        sa.CheckConstraint(
            "grammatical_range_and_accuracy_band >= 0 "
            "AND grammatical_range_and_accuracy_band <= 9 "
            "AND grammatical_range_and_accuracy_band * 2 = "
            "floor(grammatical_range_and_accuracy_band * 2)",
            name="ck_writing_evaluation_grammatical_range_and_accuracy_band",
        ),
        sa.CheckConstraint(
            "product_band >= 0 AND product_band <= 9 "
            "AND product_band * 2 = floor(product_band * 2)",
            name="ck_writing_evaluation_product_band",
        ),
        sa.CheckConstraint(
            "length(trim(feedback)) > 0",
            name="ck_writing_evaluation_feedback_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_writing_evaluation_provider_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(model)) > 0",
            name="ck_writing_evaluation_model_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(prompt_version)) > 0",
            name="ck_writing_evaluation_prompt_version_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["writing_attempts.id"],
            name="fk_writing_evaluation_attempt_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id",
            name="uq_writing_evaluation_attempt_id",
        ),
    )
    op.create_index(
        "ix_writing_evaluation_created_at",
        "writing_evaluations",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the Phase 2 writing persistence schema."""

    op.drop_index(
        "ix_writing_evaluation_created_at",
        table_name="writing_evaluations",
    )
    op.drop_table("writing_evaluations")
    op.drop_index(
        "ix_writing_attempt_created_at",
        table_name="writing_attempts",
    )
    op.drop_table("writing_attempts")
