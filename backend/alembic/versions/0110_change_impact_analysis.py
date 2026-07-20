"""Record the installed snapshot that a change project inherits.

Revision ID: 0110_change_impact_analysis
Revises: 0109_implementation_permissions
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0110_change_impact_analysis"
down_revision = "0109_implementation_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_system_implementation_project",
        sa.Column("change_source_installation_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_t_system_implementation_project_change_source",
        "t_system_implementation_project",
        ["change_source_installation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_t_system_implementation_project_change_source",
        table_name="t_system_implementation_project",
    )
    op.drop_column("t_system_implementation_project", "change_source_installation_id")
