"""岗位实习中心: 岗位匹配 intention + match 表

Revision ID: 0025_internship_match
Revises: 0024_gd_review_defense_grade_risk_archive
Create Date: 2026-07-08

新表：t_internship_intention / t_internship_match。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0025_internship_match"
down_revision = "0024_gd_review_defense_grade_risk_archive"
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

    if not _has(bind, "t_internship_intention"):
        op.create_table(
            "t_internship_intention",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("record_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("preferred_city", sa.String(100), nullable=True),
            sa.Column("preferred_industry", sa.String(100), nullable=True),
            sa.Column("preferred_company_id", sa.BigInteger(), nullable=True),
            sa.Column("preferred_position_id", sa.BigInteger(), nullable=True),
            sa.Column("intention_note", sa.String(500), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "record_id", "student_id", "batch_id",
                    "preferred_company_id", "preferred_position_id", "status"):
            op.create_index(f"ix_t_internship_intention_{col}", "t_internship_intention", [col])

    if not _has(bind, "t_internship_match"):
        op.create_table(
            "t_internship_match",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("record_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("position_id", sa.BigInteger(), nullable=False),
            sa.Column("company_id", sa.BigInteger(), nullable=False),
            sa.Column("match_type", sa.String(32), nullable=False, server_default="MANUAL"),
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("major_hit", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("enterprise_hit", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("conflict_flag", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("conflict_reason", sa.String(500), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="RECOMMENDED"),
            sa.Column("confirmed_by", sa.String(100), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("remark", sa.String(500), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "record_id", "student_id", "position_id",
                    "company_id", "match_type", "status"):
            op.create_index(f"ix_t_internship_match_{col}", "t_internship_match", [col])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_internship_match", "t_internship_intention"):
        if _has(bind, t):
            for idx in inspect(bind).get_indexes(t):
                op.drop_index(idx["name"], table_name=t)
            op.drop_table(t)
