"""Yiyang SM02 formal internship-plan identity fields.

Revision ID: ix0024
Revises: ix0023
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0024"
down_revision = "ix0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("t_internship_batch_plan", sa.Column("plan_no", sa.String(100), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("major_name", sa.String(200), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("education_level", sa.String(100), nullable=True))
    op.add_column("t_internship_batch_plan", sa.Column("subsidy_standard", sa.String(200), nullable=True))
    op.create_unique_constraint(
        "uk_ix_intern_plan_no", "t_internship_batch_plan", ["tenant_id", "plan_no"]
    )


def downgrade() -> None:
    op.drop_constraint("uk_ix_intern_plan_no", "t_internship_batch_plan", type_="unique")
    op.drop_column("t_internship_batch_plan", "subsidy_standard")
    op.drop_column("t_internship_batch_plan", "education_level")
    op.drop_column("t_internship_batch_plan", "major_name")
    op.drop_column("t_internship_batch_plan", "plan_no")
