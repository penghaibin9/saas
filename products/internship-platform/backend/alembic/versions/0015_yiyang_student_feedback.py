"""Yiyang C08/SM17 student feedback fields on the existing complaint/case ledger.

Revision ID: ix0015
Revises: ix0014
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0015"
down_revision = "ix0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("t_internship_complaint", sa.Column("title", sa.String(200), nullable=True))
    op.add_column("t_internship_complaint", sa.Column("feedback_level", sa.String(20), nullable=True))
    op.add_column("t_internship_complaint", sa.Column("image_file_ids", sa.JSON(), nullable=True))
    op.create_index(
        "ix_t_internship_complaint_feedback_level",
        "t_internship_complaint",
        ["feedback_level"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_t_internship_complaint_feedback_level",
        table_name="t_internship_complaint",
    )
    op.drop_column("t_internship_complaint", "image_file_ids")
    op.drop_column("t_internship_complaint", "feedback_level")
    op.drop_column("t_internship_complaint", "title")
