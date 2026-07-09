"""岗位实习中心 · 实习成绩五项权重表 t_internship_score_config + t_internship_final_score（P2-D）

Revision ID: 0034_internship_score
Revises: 0033_internship_student_eval
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0034_internship_score"
down_revision = "0033_internship_student_eval"
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
    if not _has(bind, "t_internship_score_config"):
        op.create_table(
            "t_internship_score_config",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("checkin_weight", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("weekly_weight", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("monthly_weight", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("enterprise_weight", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("school_weight", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("pass_line", sa.Float(), nullable=False, server_default="60"),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "batch_id"):
            op.create_index(f"ix_t_internship_score_config_{col}", "t_internship_score_config", [col])
    if not _has(bind, "t_internship_final_score"):
        op.create_table(
            "t_internship_final_score",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("checkin_score", sa.Integer(), nullable=True),
            sa.Column("weekly_score", sa.Integer(), nullable=True),
            sa.Column("monthly_score", sa.Integer(), nullable=True),
            sa.Column("enterprise_score", sa.Integer(), nullable=True),
            sa.Column("school_score", sa.Integer(), nullable=True),
            sa.Column("w_checkin", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("w_weekly", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("w_monthly", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("w_enterprise", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("w_school", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_score", sa.Float(), nullable=True),
            sa.Column("pass_line", sa.Float(), nullable=False, server_default="60"),
            sa.Column("is_pass", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("incomplete", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("incomplete_reason", sa.String(300), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING_CALC"),
            sa.Column("reviewed_by_name", sa.String(50), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("published_by_name", sa.String(50), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("remark", sa.String(500), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id", "batch_id"):
            op.create_index(f"ix_t_internship_final_score_{col}", "t_internship_final_score", [col])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_internship_final_score", "t_internship_score_config"):
        if _has(bind, t):
            for idx in inspect(bind).get_indexes(t):
                op.drop_index(idx["name"], table_name=t)
            op.drop_table(t)
