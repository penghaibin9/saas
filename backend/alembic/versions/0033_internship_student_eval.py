"""岗位实习中心 · 学生鉴定/自评表 t_internship_student_eval（P2-C）

Revision ID: 0033_internship_student_eval
Revises: 0032_internship_enterprise_eval
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0033_internship_student_eval"
down_revision = "0032_internship_enterprise_eval"
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
    if not _has(bind, "t_internship_student_eval"):
        op.create_table(
            "t_internship_student_eval",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("self_summary", sa.Text(), nullable=True),
            sa.Column("self_harvest", sa.Text(), nullable=True),
            sa.Column("self_problem", sa.Text(), nullable=True),
            sa.Column("advisor_opinion", sa.String(1000), nullable=True),
            sa.Column("mentor_opinion", sa.String(1000), nullable=True),
            sa.Column("submit_status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("school_review_status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("school_review_comment", sa.String(500), nullable=True),
            sa.Column("reviewed_by_name", sa.String(50), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("file_id", sa.String(64), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id", "batch_id"):
            op.create_index(f"ix_t_internship_student_eval_{col}", "t_internship_student_eval", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_student_eval"):
        for idx in inspect(bind).get_indexes("t_internship_student_eval"):
            op.drop_index(idx["name"], table_name="t_internship_student_eval")
        op.drop_table("t_internship_student_eval")
