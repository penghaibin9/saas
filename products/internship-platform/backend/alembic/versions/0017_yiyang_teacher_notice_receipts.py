"""Yiyang C08/TM01 teacher emergency notice receipts.

Revision ID: ix0017
Revises: ix0016
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0017"
down_revision = "ix0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_emergency_notice_teacher_receipt",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_user_id", sa.BigInteger(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=False),
        sa.Column(
            "acknowledged_channel", sa.String(30), nullable=False,
            server_default="TEACHER_MOBILE_FORCE_POPUP",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint(
            "tenant_id", "notice_id", "teacher_user_id",
            name="uk_ix_emergency_notice_teacher_receipt",
        ),
    )
    op.create_index(
        "ix_ix_emergency_notice_teacher_receipt_lookup",
        "t_internship_emergency_notice_teacher_receipt",
        ["tenant_id", "batch_id", "teacher_user_id", "acknowledged_at"],
    )
    for column in ("notice_id", "batch_id", "teacher_user_id"):
        op.create_index(
            f"ix_t_internship_emergency_notice_teacher_receipt_{column}",
            "t_internship_emergency_notice_teacher_receipt", [column],
        )


def downgrade() -> None:
    op.drop_table("t_internship_emergency_notice_teacher_receipt")
