"""Yiyang C08/SM16 internship exemption application fields.

Revision ID: ix0013
Revises: ix0012
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0013"
down_revision = "ix0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_internship_application",
        sa.Column("exemption_type", sa.String(30), nullable=True),
    )
    op.add_column(
        "t_internship_application",
        sa.Column("exemption_reason", sa.String(500), nullable=True),
    )
    op.add_column(
        "t_internship_application",
        sa.Column("exemption_destination", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("t_internship_application", "exemption_destination")
    op.drop_column("t_internship_application", "exemption_reason")
    op.drop_column("t_internship_application", "exemption_type")
