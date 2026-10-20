"""Yiyang C08/G16 emergency notice read receipts.

Revision ID: ix0012
Revises: ix0011
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0012"
down_revision = "ix0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_emergency_notice_receipt",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=False),
        sa.Column(
            "acknowledged_channel", sa.String(30), nullable=False,
            server_default="MOBILE_FORCE_POPUP",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint(
            "tenant_id", "notice_id", "student_id",
            name="uk_ix_emergency_notice_receipt",
        ),
    )
    op.create_index(
        "ix_ix_emergency_notice_receipt_lookup",
        "t_internship_emergency_notice_receipt",
        ["tenant_id", "batch_id", "student_id", "acknowledged_at"],
    )
    op.create_index(
        "ix_t_internship_emergency_notice_receipt_notice_id",
        "t_internship_emergency_notice_receipt", ["notice_id"],
    )
    op.create_index(
        "ix_t_internship_emergency_notice_receipt_batch_id",
        "t_internship_emergency_notice_receipt", ["batch_id"],
    )
    op.create_index(
        "ix_t_internship_emergency_notice_receipt_student_id",
        "t_internship_emergency_notice_receipt", ["student_id"],
    )


def downgrade() -> None:
    op.drop_table("t_internship_emergency_notice_receipt")
