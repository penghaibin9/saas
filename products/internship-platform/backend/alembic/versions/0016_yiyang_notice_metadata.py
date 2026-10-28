"""Yiyang C08/SM01 notice type, urgency, validity and attachments.

Revision ID: ix0016
Revises: ix0015
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0016"
down_revision = "ix0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_internship_emergency_notice",
        sa.Column("notice_type", sa.String(30), nullable=False, server_default="NOTICE"),
    )
    op.add_column(
        "t_internship_emergency_notice",
        sa.Column("urgency", sa.String(20), nullable=False, server_default="NORMAL"),
    )
    op.add_column(
        "t_internship_emergency_notice",
        sa.Column("valid_from", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "t_internship_emergency_notice",
        sa.Column("valid_until", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "t_internship_emergency_notice",
        sa.Column("attachment_file_ids_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("t_internship_emergency_notice", "attachment_file_ids_json")
    op.drop_column("t_internship_emergency_notice", "valid_until")
    op.drop_column("t_internship_emergency_notice", "valid_from")
    op.drop_column("t_internship_emergency_notice", "urgency")
    op.drop_column("t_internship_emergency_notice", "notice_type")
