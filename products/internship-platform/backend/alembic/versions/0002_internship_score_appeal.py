"""Add Standalone internship score appeal table.

Revision ID: ix0002
Revises: ix0001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0002"
down_revision = "ix0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_score_appeal",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("internship_id", sa.BigInteger(), nullable=False),
        sa.Column("score_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("wo_type", sa.String(30), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("handler", sa.String(100), nullable=True),
        sa.Column("trail_json", sa.JSON(), nullable=True),
        sa.Column("close_time", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_t_internship_score_appeal_tenant_id", "t_internship_score_appeal", ["tenant_id"])
    op.create_index("ix_t_internship_score_appeal_student_id", "t_internship_score_appeal", ["student_id"])
    op.create_index("ix_t_internship_score_appeal_internship_id", "t_internship_score_appeal", ["internship_id"])
    op.create_index("ix_t_internship_score_appeal_score_id", "t_internship_score_appeal", ["score_id"])
    op.create_index(
        "ix_score_appeal_record_status",
        "t_internship_score_appeal",
        ["tenant_id", "internship_id", "status", "id"],
    )
    op.create_index(
        "ix_score_appeal_student",
        "t_internship_score_appeal",
        ["tenant_id", "student_id", "id"],
    )


def downgrade() -> None:
    op.drop_table("t_internship_score_appeal")
