"""Yiyang C08/AP03 internship plan procurement fields.

Revision ID: ix0020
Revises: ix0019
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0020"
down_revision = "ix0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("t_internship_batch_plan", sa.Column("internship_type", sa.String(30), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("target_audience", sa.String(500), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("plan_requirements", sa.Text(), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("assessment_content", sa.Text(), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("responsible_name", sa.String(100), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("attachment_file_ids_json", sa.JSON(), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("template_code", sa.String(80), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("basic_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("rules_snapshot_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    for name in (
        "rules_snapshot_json",
        "basic_snapshot_json",
        "template_code",
        "attachment_file_ids_json",
        "responsible_name",
        "assessment_content",
        "plan_requirements",
        "target_audience",
        "internship_type",
    ):
        op.drop_column("t_internship_batch_plan", name)
