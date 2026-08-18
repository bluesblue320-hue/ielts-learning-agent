"""Add Phase 4 Writing practice persistence.

Revision ID: 0004_writing_practice
Revises: 0003_learning
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_writing_practice"
down_revision: str | None = "0003_learning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CANONICAL_SKILLS = (
    "'task_response'",
    "'coherence_and_cohesion'",
    "'lexical_resource'",
    "'grammatical_range_and_accuracy'",
)


def _skill_check(column: str) -> str:
    values = ", ".join(_CANONICAL_SKILLS)
    return f"{column} IN ({values})"


def upgrade() -> None:
    """Add the Phase 4 ownership candidate key and the writing_practices table.

    Exactly two additive changes: (1) the narrow Phase 4 ownership candidate
    key on practice_recommendations, and (2) the writing_practices table and
    its Phase 4 constraints. No other Phase 2/3 table is altered.
    """

    # 1. Phase 4 ownership candidate key on practice_recommendations.
    op.create_unique_constraint(
        "uq_practice_recommendation_id_learner",
        "practice_recommendations",
        ["id", "learner_id"],
    )

    # 2. writing_practices.
    op.create_table(
        "writing_practices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "learner_id",
            sa.BigInteger(),
            sa.ForeignKey("learners.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recommendation_id", sa.BigInteger(), nullable=False),
        sa.Column("target_skill", sa.String(length=64), nullable=False),
        sa.Column("practice_type", sa.String(length=64), nullable=False),
        sa.Column("question", sa.String(length=400), nullable=False),
        sa.Column("focus_objective", sa.String(length=300), nullable=False),
        sa.Column("instructions", postgresql.JSONB(), nullable=False),
        sa.Column("checkpoints", postgresql.JSONB(), nullable=False),
        sa.Column("generator_policy_version", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("thinking_mode", sa.String(length=16), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
        sa.Column("submission_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("claim_token", sa.String(length=128), nullable=True),
        sa.Column(
            "attempt_id",
            sa.BigInteger(),
            sa.ForeignKey("writing_attempts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # At most one durable practice per eligible recommendation.
        sa.UniqueConstraint(
            "recommendation_id",
            name="uq_writing_practice_recommendation_id",
        ),
        # One attempt belongs to at most one practice (NULLs distinct).
        sa.UniqueConstraint("attempt_id", name="uq_writing_practice_attempt_id"),
        # Database-enforced ownership: recommendation must belong to the same
        # learner as the practice row.
        sa.ForeignKeyConstraint(
            ["recommendation_id", "learner_id"],
            ["practice_recommendations.id", "practice_recommendations.learner_id"],
            name="fk_writing_practice_recommendation_ownership",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ('generated', 'submission_in_progress', 'submitted')",
            name="ck_writing_practice_lifecycle_state",
        ),
        sa.CheckConstraint(
            "length(trim(question)) > 0 AND length(question) <= 400",
            name="ck_writing_practice_question_length",
        ),
        sa.CheckConstraint(
            "length(trim(focus_objective)) > 0 AND length(focus_objective) <= 300",
            name="ck_writing_practice_objective_length",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(instructions) = 'array'",
            name="ck_writing_practice_instructions_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(checkpoints) = 'array'",
            name="ck_writing_practice_checkpoints_array",
        ),
        sa.CheckConstraint(
            "length(trim(generator_policy_version)) > 0",
            name="ck_writing_practice_generator_policy_version_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_writing_practice_provider_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(model)) > 0",
            name="ck_writing_practice_model_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(prompt_version)) > 0",
            name="ck_writing_practice_prompt_version_nonblank",
        ),
        sa.CheckConstraint(
            "thinking_mode IN ('enabled', 'disabled')",
            name="ck_writing_practice_thinking_mode",
        ),
        sa.CheckConstraint(
            "(lifecycle_state = 'submitted' AND attempt_id IS NOT NULL)"
            " OR (lifecycle_state IN ('generated', 'submission_in_progress')"
            " AND attempt_id IS NULL)",
            name="ck_writing_practice_attempt_nullability",
        ),
        sa.Index(
            "ix_writing_practice_learner_state",
            "learner_id",
            "lifecycle_state",
        ),
    )


def downgrade() -> None:
    """Remove ONLY Phase 4 additions.

    Drop writing_practices and its constraints, then drop the Phase 4-added
    ownership candidate key from practice_recommendations. No pre-existing
    Phase 3 constraint is removed or altered.
    """

    op.drop_table("writing_practices")
    op.drop_constraint(
        "uq_practice_recommendation_id_learner",
        "practice_recommendations",
        type_="unique",
    )
