"""岗位实习中心 · 教师巡访表 t_internship_visit（P1-Stage2）

Revision ID: 0029_internship_visit
Revises: 0028_internship_guidance
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0029_internship_visit"
down_revision = "0028_internship_guidance"
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
    if not _has(bind, "t_internship_visit"):
        op.create_table(
            "t_internship_visit",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("advisor_name", sa.String(50), nullable=True),
            sa.Column("enterprise_name", sa.String(200), nullable=True),
            sa.Column("visit_at", sa.DateTime(), nullable=True),
            sa.Column("method", sa.String(20), nullable=False, server_default="ONSITE"),
            sa.Column("enterprise_feedback", sa.String(1000), nullable=True),
            sa.Column("student_feedback", sa.String(1000), nullable=True),
            sa.Column("safety_issue", sa.String(500), nullable=True),
            sa.Column("rectify_require", sa.String(500), nullable=True),
            sa.Column("rectify_deadline", sa.String(10), nullable=True),
            sa.Column("rectify_status", sa.String(20), nullable=False, server_default="NONE"),
            sa.Column("monthly_report", sa.Text(), nullable=True),
            sa.Column("file_id", sa.String(64), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id"):
            op.create_index(f"ix_t_internship_visit_{col}", "t_internship_visit", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_visit"):
        for idx in inspect(bind).get_indexes("t_internship_visit"):
            op.drop_index(idx["name"], table_name="t_internship_visit")
        op.drop_table("t_internship_visit")
