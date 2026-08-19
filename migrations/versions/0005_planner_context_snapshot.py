"""Add the Phase 7 planner audit snapshot column.

Revision ID: 0005_planner_context_snapshot
Revises: 0004_writing_practice
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_planner_context_snapshot"
down_revision: str | None = "0004_writing_practice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SNAPSHOT_CHECK = "ck_practice_recommendation_planner_context_snapshot_object"


def upgrade() -> None:
    """Add only the nullable internal P7 audit envelope column.

    The database boundary intentionally checks just the durable JSONB container
    shape. The versioned v1/v2 snapshot-presence matrix and tie semantics are
    strict domain/application invariants, not a duplicated SQL planner.
    """

    op.add_column(
        "practice_recommendations",
        sa.Column("planner_context_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.create_check_constraint(
        _SNAPSHOT_CHECK,
        "practice_recommendations",
        "planner_context_snapshot IS NULL OR "
        "jsonb_typeof(planner_context_snapshot) = 'object'",
    )


def downgrade() -> None:
    """Remove only the additive Phase 7 column and its check constraint."""

    op.drop_constraint(
        _SNAPSHOT_CHECK,
        "practice_recommendations",
        type_="check",
    )
    op.drop_column("practice_recommendations", "planner_context_snapshot")
