"""岗位实习中心 · 指导记录表 t_internship_guidance（P1-Stage2）

Revision ID: 0028_internship_guidance
Revises: 0027_internship_makeup
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0028_internship_guidance"
down_revision = "0027_internship_makeup"
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
    if not _has(bind, "t_internship_guidance"):
        op.create_table(
            "t_internship_guidance",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("advisor_name", sa.String(50), nullable=True),
            sa.Column("method", sa.String(20), nullable=False, server_default="ONSITE"),
            sa.Column("topic", sa.String(200), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("problem_type", sa.String(50), nullable=True),
            sa.Column("suggestion", sa.String(1000), nullable=True),
            sa.Column("next_follow_date", sa.String(10), nullable=True),
            sa.Column("to_risk", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("notify_counselor", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("file_id", sa.String(64), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="NORMAL"),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id"):
            op.create_index(f"ix_t_internship_guidance_{col}", "t_internship_guidance", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_guidance"):
        for idx in inspect(bind).get_indexes("t_internship_guidance"):
            op.drop_index(idx["name"], table_name="t_internship_guidance")
        op.drop_table("t_internship_guidance")
