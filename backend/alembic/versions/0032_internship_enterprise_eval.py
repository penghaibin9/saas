"""岗位实习中心 · 企业评价表 t_internship_enterprise_eval（P2-B）

Revision ID: 0032_internship_enterprise_eval
Revises: 0031_internship_agreement
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0032_internship_enterprise_eval"
down_revision = "0031_internship_agreement"
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
    if not _has(bind, "t_internship_enterprise_eval"):
        op.create_table(
            "t_internship_enterprise_eval",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("position_name", sa.String(100), nullable=True),
            sa.Column("mentor_name", sa.String(50), nullable=True),
            sa.Column("attendance_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skill_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("attitude_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("collaboration_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("safety_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("overall_comment", sa.Text(), nullable=True),
            sa.Column("recommend_hire", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(20), nullable=False, server_default="SCHOOL_RECORDED"),
            sa.Column("submit_status", sa.String(20), nullable=False, server_default="SUBMITTED"),
            sa.Column("school_review_status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("school_review_comment", sa.String(500), nullable=True),
            sa.Column("reviewed_by_name", sa.String(50), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("file_id", sa.String(64), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id", "batch_id"):
            op.create_index(f"ix_t_internship_enterprise_eval_{col}", "t_internship_enterprise_eval", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_enterprise_eval"):
        for idx in inspect(bind).get_indexes("t_internship_enterprise_eval"):
            op.drop_index(idx["name"], table_name="t_internship_enterprise_eval")
        op.drop_table("t_internship_enterprise_eval")
