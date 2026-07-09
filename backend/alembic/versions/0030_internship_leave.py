"""岗位实习中心 · 实习请假表 t_internship_leave（P1-Stage3）

Revision ID: 0030_internship_leave
Revises: 0029_internship_visit
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0030_internship_leave"
down_revision = "0029_internship_visit"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
_COMMON = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")


def _common_cols():
    return [
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
    ]


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, "t_internship_leave"):
        op.create_table(
            "t_internship_leave",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("leave_type", sa.String(20), nullable=False, server_default="PERSONAL"),
            sa.Column("start_date", sa.String(10), nullable=False),
            sa.Column("end_date", sa.String(10), nullable=False),
            sa.Column("days", sa.Float(), nullable=False, server_default="1"),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("apply_by_name", sa.String(50), nullable=True),
            sa.Column("review_by_name", sa.String(50), nullable=True),
            sa.Column("review_at", sa.DateTime(), nullable=True),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("file_id", sa.String(64), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id"):
            op.create_index(f"ix_t_internship_leave_{col}", "t_internship_leave", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_leave"):
        for idx in inspect(bind).get_indexes("t_internship_leave"):
            op.drop_index(idx["name"], table_name="t_internship_leave")
        op.drop_table("t_internship_leave")
