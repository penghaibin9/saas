"""岗位实习中心 · 补卡申请表 t_internship_makeup（P1-Stage1）

Revision ID: 0027_internship_makeup
Revises: 0026_gd_batch5_9
Create Date: 2026-07-09

新表：t_internship_makeup（补卡申请工作流）。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0027_internship_makeup"
down_revision = "0026_gd_batch5_9"
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


def _has(bind, table: str) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, "t_internship_makeup"):
        op.create_table(
            "t_internship_makeup",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("checkin_date", sa.String(10), nullable=False),
            sa.Column("makeup_type", sa.String(20), nullable=False, server_default="MISSING"),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("apply_by_name", sa.String(50), nullable=True),
            sa.Column("review_by_name", sa.String(50), nullable=True),
            sa.Column("review_at", sa.DateTime(), nullable=True),
            sa.Column("review_comment", sa.String(500), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id", "status"):
            op.create_index(f"ix_t_internship_makeup_{col}", "t_internship_makeup", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_makeup"):
        for idx in inspect(bind).get_indexes("t_internship_makeup"):
            op.drop_index(idx["name"], table_name="t_internship_makeup")
        op.drop_table("t_internship_makeup")
