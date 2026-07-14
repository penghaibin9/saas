"""13B 课堂考勤：建表 t_aa_attendance_session（移动端教师按行政班逐场次考勤）。

全新业务表，downgrade drop。幂等：inspect 判表。

Revision ID: 0081_13b_attendance
Revises: 0080_13b_classroom_booking
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0081_13b_attendance"
down_revision = "0080_13b_classroom_booking"
branch_labels = None
depends_on = None

TABLE = "t_aa_attendance_session"


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("class_id", sa.BigInteger()),
            sa.Column("course_name", sa.String(200)),
            sa.Column("term_code", sa.String(50)),
            sa.Column("teacher_key", sa.String(100)),
            sa.Column("session_date", sa.String(20), nullable=False),
            sa.Column("slot_no", sa.Integer()),
            sa.Column("roster_json", sa.Text()),
            sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("present_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("absent_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        op.create_index("ix_aa_attendance_class", TABLE, ["tenant_id", "class_id", "session_date"])
        op.create_index("ix_aa_attendance_teacher", TABLE, ["tenant_id", "teacher_key"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, TABLE):
        op.drop_table(TABLE)
