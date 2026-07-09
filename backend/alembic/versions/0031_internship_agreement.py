"""岗位实习中心 · 三方协议签署实例表 t_internship_agreement（P2-A）

Revision ID: 0031_internship_agreement
Revises: 0030_internship_leave
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0031_internship_agreement"
down_revision = "0030_internship_leave"
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
    if not _has(bind, "t_internship_agreement"):
        op.create_table(
            "t_internship_agreement",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("template_id", sa.BigInteger(), nullable=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("enterprise_name", sa.String(200), nullable=True),
            sa.Column("position_name", sa.String(100), nullable=True),
            sa.Column("student_confirm_status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("student_confirm_at", sa.DateTime(), nullable=True),
            sa.Column("enterprise_confirm_status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("enterprise_confirm_at", sa.DateTime(), nullable=True),
            sa.Column("enterprise_confirm_by", sa.String(50), nullable=True),
            sa.Column("school_confirm_status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("school_confirm_at", sa.DateTime(), nullable=True),
            sa.Column("school_confirm_by", sa.String(50), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("reject_reason", sa.String(500), nullable=True),
            sa.Column("file_id", sa.String(64), nullable=True),
            sa.Column("esign_status", sa.String(20), nullable=False, server_default="NONE"),
            sa.Column("remark", sa.String(500), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id", "template_id", "batch_id", "status"):
            op.create_index(f"ix_t_internship_agreement_{col}", "t_internship_agreement", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_agreement"):
        for idx in inspect(bind).get_indexes("t_internship_agreement"):
            op.drop_index(idx["name"], table_name="t_internship_agreement")
        op.drop_table("t_internship_agreement")
