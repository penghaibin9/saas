"""Yiyang C08/SM14 intelligent support sessions.

Revision ID: ix0014
Revises: ix0013
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0014"
down_revision = "ix0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_support_session",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("internship_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("unresolved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_question", sa.Text(), nullable=True),
        sa.Column("last_answer", sa.Text(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("transferred_risk_id", sa.BigInteger(), nullable=True),
        sa.Column("transferred_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index(
        "ix_ix_support_student_status",
        "t_internship_support_session",
        ["tenant_id", "internship_id", "student_id", "status", "id"],
    )
    for column in ("internship_id", "batch_id", "student_id", "transferred_risk_id"):
        op.create_index(
            f"ix_t_internship_support_session_{column}",
            "t_internship_support_session", [column],
        )


def downgrade() -> None:
    op.drop_table("t_internship_support_session")
