"""Yiyang C08/AP06 notice audience scope by college.

Revision ID: ix0018
Revises: ix0017
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0018"
down_revision = "ix0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_internship_emergency_notice",
        sa.Column("audience_scope", sa.String(20), nullable=False, server_default="ALL"),
    )
    op.add_column(
        "t_internship_emergency_notice",
        sa.Column("recipient_college_ids_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("t_internship_emergency_notice", "recipient_college_ids_json")
    op.drop_column("t_internship_emergency_notice", "audience_scope")
