"""Add Phase 3 learning persistence tables.

Revision ID: 0003_learning
Revises: 0002_writing
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_learning"
down_revision: str | None = "0002_writing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CANONICAL_SKILLS = (
    "'task_response'",
    "'coherence_and_cohesion'",
    "'lexical_resource'",
    "'grammatical_range_and_accuracy'",
)

_PRACTICE_REASON_SEQUENCES = (
    "'[\"largest_target_gap\"]'::jsonb",
    "'[\"largest_target_gap\",\"priority_tiebreak\"]'::jsonb",
    "'[\"largest_target_gap\",\"insufficient_evidence\"]'::jsonb",
    "'[\"largest_target_gap\",\"priority_tiebreak\",\"insufficient_evidence\"]'::jsonb",
)

_NO_PRACTICE_REASON_SEQUENCES = (
    "'[\"target_achieved\"]'::jsonb",
    "'[\"target_achieved\",\"insufficient_evidence\"]'::jsonb",
    "'[\"cold_start\"]'::jsonb",
    "'[\"incomplete_state\"]'::jsonb",
    "'[\"target_unset\"]'::jsonb",
)


def _skill_check(column: str) -> str:
    values = ", ".join(_CANONICAL_SKILLS)
    return f"{column} IN ({values})"


def _half_band_check(column: str) -> str:
    return (
        f"{column} >= 0 AND {column} <= 9 "
        f"AND {column} * 2 = floor({column} * 2)"
    )


def _reason_sequences() -> str:
    return ", ".join(_PRACTICE_REASON_SEQUENCES + _NO_PRACTICE_REASON_SEQUENCES)


def upgrade() -> None:
    """Create the Phase 3 learning persistence schema."""

    # 1. learners (depends on nothing)
    op.create_table(
        "learners",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("writing_target_band", sa.Numeric(2, 1), nullable=False),
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
        sa.CheckConstraint(
            _half_band_check("writing_target_band"),
            name="ck_learner_writing_target_band",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. learning_updates (depends on learners, writing_evaluations)
    op.create_table(
        "learning_updates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.BigInteger(), nullable=False),
        sa.Column("writing_evaluation_id", sa.BigInteger(), nullable=False),
        sa.Column("skill_taxonomy_version", sa.String(length=64), nullable=False),
        sa.Column("state_policy_version", sa.String(length=64), nullable=False),
        sa.Column("planner_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(skill_taxonomy_version)) > 0",
            name="ck_learning_update_skill_taxonomy_version_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(state_policy_version)) > 0",
            name="ck_learning_update_state_policy_version_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(planner_version)) > 0",
            name="ck_learning_update_planner_version_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_learning_update_learner_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["writing_evaluation_id"],
            ["writing_evaluations.id"],
            name="fk_learning_update_writing_evaluation_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "learner_id",
            name="uq_learning_update_learner_identity",
        ),
        sa.UniqueConstraint(
            "id",
            "learner_id",
            "writing_evaluation_id",
            name="uq_learning_update_identity",
        ),
        sa.UniqueConstraint(
            "writing_evaluation_id",
            name="uq_learning_update_writing_evaluation_id",
        ),
    )

    # 3. learning_evidence (depends on learning_updates, writing_attempts)
    op.create_table(
        "learning_evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("learning_update_id", sa.BigInteger(), nullable=False),
        sa.Column("learner_id", sa.BigInteger(), nullable=False),
        sa.Column("writing_evaluation_id", sa.BigInteger(), nullable=False),
        sa.Column("skill", sa.String(length=64), nullable=False),
        sa.Column("observed_band", sa.Numeric(2, 1), nullable=False),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_attempt_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("rubric_version", sa.String(length=64), nullable=False),
        sa.Column("scoring_policy_version", sa.String(length=64), nullable=False),
        sa.Column("thinking_mode", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _skill_check("skill"),
            name="ck_learning_evidence_skill",
        ),
        sa.CheckConstraint(
            _half_band_check("observed_band"),
            name="ck_learning_evidence_observed_band",
        ),
        sa.CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_learning_evidence_provider_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(model)) > 0",
            name="ck_learning_evidence_model_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(prompt_version)) > 0",
            name="ck_learning_evidence_prompt_version_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(rubric_version)) > 0",
            name="ck_learning_evidence_rubric_version_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(scoring_policy_version)) > 0",
            name="ck_learning_evidence_scoring_policy_version_nonblank",
        ),
        sa.CheckConstraint(
            "thinking_mode IN ('enabled', 'disabled')",
            name="ck_learning_evidence_thinking_mode",
        ),
        sa.ForeignKeyConstraint(
            ["learning_update_id", "learner_id", "writing_evaluation_id"],
            [
                "learning_updates.id",
                "learning_updates.learner_id",
                "learning_updates.writing_evaluation_id",
            ],
            name="fk_learning_evidence_learning_update_ownership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_attempt_id"],
            ["writing_attempts.id"],
            name="fk_learning_evidence_source_attempt_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_update_id",
            "skill",
            name="uq_learning_evidence_update_skill",
        ),
        sa.UniqueConstraint(
            "id",
            "learner_id",
            "skill",
            name="uq_learning_evidence_identity",
        ),
    )
    op.create_index(
        "ix_learning_evidence_canonical_replay",
        "learning_evidence",
        ["learner_id", "skill", "source_created_at", "source_attempt_id"],
        unique=False,
    )

    # 4. learner_skill_states (depends on learners, learning_evidence)
    op.create_table(
        "learner_skill_states",
        sa.Column("learner_id", sa.BigInteger(), nullable=False),
        sa.Column("skill", sa.String(length=64), nullable=False),
        sa.Column("estimated_band", sa.Numeric(3, 2), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("state_policy_version", sa.String(length=64), nullable=False),
        sa.Column("last_evidence_id", sa.BigInteger(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _skill_check("skill"),
            name="ck_learner_skill_state_skill",
        ),
        sa.CheckConstraint(
            "estimated_band >= 0 AND estimated_band <= 9",
            name="ck_learner_skill_state_estimated_band_range",
        ),
        sa.CheckConstraint(
            "evidence_count >= 0",
            name="ck_learner_skill_state_evidence_count_nonnegative",
        ),
        sa.CheckConstraint(
            "revision >= 0",
            name="ck_learner_skill_state_revision_nonnegative",
        ),
        sa.CheckConstraint(
            "length(trim(state_policy_version)) > 0",
            name="ck_learner_skill_state_state_policy_version_nonblank",
        ),
        sa.CheckConstraint(
            "(evidence_count = 0 AND estimated_band IS NULL "
            "AND last_evidence_id IS NULL AND revision = 0)"
            " OR (evidence_count > 0 AND estimated_band IS NOT NULL "
            "AND last_evidence_id IS NOT NULL AND revision >= 1)",
            name="ck_learner_skill_state_observed_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_learner_skill_state_learner_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["last_evidence_id", "learner_id", "skill"],
            [
                "learning_evidence.id",
                "learning_evidence.learner_id",
                "learning_evidence.skill",
            ],
            name="fk_learner_skill_state_last_evidence_ownership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("learner_id", "skill"),
    )

    # 5. practice_recommendations (depends on learners, learning_updates)
    op.create_table(
        "practice_recommendations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("learning_update_id", sa.BigInteger(), nullable=False),
        sa.Column("learner_id", sa.BigInteger(), nullable=False),
        sa.Column("decision_type", sa.String(length=16), nullable=False),
        sa.Column("target_skill", sa.String(length=64), nullable=True),
        sa.Column("learner_target_band", sa.Numeric(2, 1), nullable=True),
        sa.Column("current_estimate", sa.Numeric(3, 2), nullable=True),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=False),
        sa.Column("planner_version", sa.String(length=64), nullable=False),
        sa.Column("state_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision_type IN ('practice', 'no_practice')",
            name="ck_practice_recommendation_decision_type",
        ),
        sa.CheckConstraint(
            f"target_skill IS NULL OR {_skill_check('target_skill')}",
            name="ck_practice_recommendation_target_skill",
        ),
        sa.CheckConstraint(
            "learner_target_band IS NULL OR "
            + _half_band_check("learner_target_band"),
            name="ck_practice_recommendation_learner_target_band",
        ),
        sa.CheckConstraint(
            "current_estimate IS NULL OR "
            "(current_estimate >= 0 AND current_estimate <= 9)",
            name="ck_practice_recommendation_current_estimate_range",
        ),
        sa.CheckConstraint(
            "length(trim(planner_version)) > 0",
            name="ck_practice_recommendation_planner_version_nonblank",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reason_codes) = 'array'",
            name="ck_practice_recommendation_reason_codes_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(state_snapshot) = 'object'",
            name="ck_practice_recommendation_state_snapshot_object",
        ),
        sa.CheckConstraint(
            f"reason_codes IN ({_reason_sequences()})",
            name="ck_practice_recommendation_reason_sequences",
        ),
        sa.CheckConstraint(
            "(decision_type = 'practice' AND reason_codes IN ("
            + ", ".join(_PRACTICE_REASON_SEQUENCES)
            + ")) OR (decision_type = 'no_practice' AND reason_codes IN ("
            + ", ".join(_NO_PRACTICE_REASON_SEQUENCES)
            + "))",
            name="ck_practice_recommendation_reason_decision",
        ),
        sa.CheckConstraint(
            "(reason_codes = '[\"target_unset\"]'::jsonb "
            "AND learner_target_band IS NULL)"
            " OR (reason_codes <> '[\"target_unset\"]'::jsonb "
            "AND learner_target_band IS NOT NULL)",
            name="ck_practice_recommendation_target_band_nullability",
        ),
        sa.CheckConstraint(
            "(decision_type = 'practice' AND target_skill IS NOT NULL "
            "AND learner_target_band IS NOT NULL AND current_estimate IS NOT NULL)"
            " OR (decision_type = 'no_practice' AND target_skill IS NULL "
            "AND current_estimate IS NULL)",
            name="ck_practice_recommendation_decision_shape",
        ),
        sa.CheckConstraint(
            "state_snapshot ? 'task_response'"
            " AND state_snapshot ? 'coherence_and_cohesion'"
            " AND state_snapshot ? 'lexical_resource'"
            " AND state_snapshot ? 'grammatical_range_and_accuracy'",
            name="ck_practice_recommendation_snapshot_skills",
        ),
        sa.ForeignKeyConstraint(
            ["learning_update_id", "learner_id"],
            ["learning_updates.id", "learning_updates.learner_id"],
            name="fk_practice_recommendation_learning_update_ownership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_practice_recommendation_learner_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_update_id",
            name="uq_practice_recommendation_learning_update_id",
        ),
    )


def downgrade() -> None:
    """Remove the Phase 3 learning persistence schema."""

    op.drop_table("practice_recommendations")
    op.drop_table("learner_skill_states")
    op.drop_index(
        "ix_learning_evidence_canonical_replay",
        table_name="learning_evidence",
    )
    op.drop_table("learning_evidence")
    op.drop_table("learning_updates")
    op.drop_table("learners")
