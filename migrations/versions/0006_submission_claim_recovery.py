"""Add durable recovery timestamps to Writing practice submission claims.

Revision ID: 0006_submission_claim_recovery
Revises: 0005_planner_context_snapshot
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_submission_claim_recovery"
down_revision: str | None = "0005_planner_context_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATE_MATRIX_CHECK = "ck_writing_practice_submission_state_matrix"


def upgrade() -> None:
    """Add the recoverable 300-second claim lease without a server default."""

    op.add_column(
        "writing_practices",
        sa.Column("submission_claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Pre-P8 claims had no lease start; make them recoverable on their first
    # explicit matching retry.
    op.execute(
        "UPDATE writing_practices "
        "SET submission_claimed_at = CURRENT_TIMESTAMP - INTERVAL '301 seconds' "
        "WHERE lifecycle_state = 'submission_in_progress' "
        "AND submission_claimed_at IS NULL"
    )
    op.create_check_constraint(
        _STATE_MATRIX_CHECK,
        "writing_practices",
        "(lifecycle_state = 'generated' "
        "AND submission_fingerprint IS NULL "
        "AND claim_token IS NULL "
        "AND submission_claimed_at IS NULL "
        "AND attempt_id IS NULL) "
        "OR (lifecycle_state = 'submission_in_progress' "
        "AND submission_fingerprint IS NOT NULL "
        "AND claim_token IS NOT NULL "
        "AND submission_claimed_at IS NOT NULL "
        "AND attempt_id IS NULL) "
        "OR (lifecycle_state = 'submitted' "
        "AND submission_fingerprint IS NOT NULL "
        "AND claim_token IS NULL "
        "AND submission_claimed_at IS NULL "
        "AND attempt_id IS NOT NULL)",
    )


def downgrade() -> None:
    """Remove only the P8 lease timestamp and its exact state check."""

    op.drop_constraint(_STATE_MATRIX_CHECK, "writing_practices", type_="check")
    op.drop_column("writing_practices", "submission_claimed_at")
