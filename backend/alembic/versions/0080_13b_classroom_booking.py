"""13B 教室预约：建表 t_aa_classroom_booking（教室占用登记，同教室同日同节次冲突检测）。

全新业务表，downgrade drop。幂等：inspect 判表。

Revision ID: 0080_13b_classroom_booking
Revises: 0079_13b_textbook_fee_partial
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0080_13b_classroom_booking"
down_revision = "0079_13b_textbook_fee_partial"
branch_labels = None
depends_on = None

TABLE = "t_aa_classroom_booking"


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("classroom_id", sa.BigInteger(), nullable=False),
            sa.Column("classroom_text", sa.String(100)),
            sa.Column("booking_date", sa.String(20), nullable=False),
            sa.Column("slot_no", sa.Integer(), nullable=False),
            sa.Column("purpose", sa.String(300)),
            sa.Column("applicant_key", sa.String(100)),
            sa.Column("applicant_name", sa.String(100)),
            sa.Column("review_reason", sa.String(300)),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        op.create_index("ix_aa_classroom_booking", TABLE, ["tenant_id", "classroom_id", "booking_date"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, TABLE):
        op.drop_table(TABLE)
