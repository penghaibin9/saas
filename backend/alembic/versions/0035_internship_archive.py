"""岗位实习中心 · 实习归档表 t_internship_archive（P3-A）

Revision ID: 0035_internship_archive
Revises: 0034_internship_score
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0035_internship_archive"
down_revision = "0034_internship_score"
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
    if not _has(bind, "t_internship_archive"):
        op.create_table(
            "t_internship_archive",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("completeness", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("missing_items", sa.String(500), nullable=True),
            sa.Column("material_snapshot", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="ARCHIVED"),
            sa.Column("package_file_id", sa.String(64), nullable=True),
            sa.Column("archived_by_name", sa.String(50), nullable=True),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.Column("remark", sa.String(500), nullable=True),
            *_common_cols(),
            **_COMMON,
        )
        for col in ("tenant_id", "internship_id", "student_id", "batch_id"):
            op.create_index(f"ix_t_internship_archive_{col}", "t_internship_archive", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_archive"):
        for idx in inspect(bind).get_indexes("t_internship_archive"):
            op.drop_index(idx["name"], table_name="t_internship_archive")
        op.drop_table("t_internship_archive")
