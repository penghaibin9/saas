"""Persist an immutable implementation acceptance summary.

Revision ID: 0111_immutable_acceptance_summary
Revises: 0110_change_impact_analysis
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0111_immutable_acceptance_summary"
down_revision = "0110_change_impact_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("t_system_implementation_project", sa.Column("acceptance_digest", sa.String(length=64), nullable=True))
    op.add_column("t_system_implementation_project", sa.Column("acceptance_summary", sa.JSON(), nullable=True))
    op.create_unique_constraint("uk_sys_impl_acceptance_digest", "t_system_implementation_project", ["acceptance_digest"])


def downgrade() -> None:
    op.drop_constraint("uk_sys_impl_acceptance_digest", "t_system_implementation_project", type_="unique")
    op.drop_column("t_system_implementation_project", "acceptance_summary")
    op.drop_column("t_system_implementation_project", "acceptance_digest")
