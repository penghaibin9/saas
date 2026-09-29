"""Yiyang AP04 student multi-plan assignment.

Revision ID: ix0021
Revises: ix0020
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0021"
down_revision = "ix0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_plan_assignment",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("internship_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("plan_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("plan_batch_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("assignment_source", sa.String(30), nullable=False, server_default="MANUAL"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("assigned_by_name", sa.String(100), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.Column("remove_reason", sa.String(500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "internship_id", "plan_id",
            name="uk_ix_plan_assignment_internship_plan",
        ),
    )
    op.create_index(
        "ix_ix_plan_assignment_active",
        "t_internship_plan_assignment",
        ["tenant_id", "internship_id", "status", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_ix_plan_assignment_active", table_name="t_internship_plan_assignment")
    op.drop_table("t_internship_plan_assignment")
