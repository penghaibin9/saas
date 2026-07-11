"""公共 Excel 底座: 通用导入记录表 t_excel_import_job

Revision ID: 0015_excel_import_job
Revises: 0014_13b_p6_graduation_audit
Create Date: 2026-07-07

跨模块共用导入作业台账。幂等：inspect 已存在则跳过（与既有迁移同风格）。
仅本底座通用表，不与业务表耦合。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0015_excel_import_job"
down_revision = "0014_13b_p6_graduation_audit"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
T = "t_excel_import_job"


def _has(bind, table):
    return table in inspect(bind).get_table_names()


def _common_cols():
    return [sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False)]


def upgrade() -> None:
    bind = op.get_bind()
    if _has(bind, T):
        return
    op.create_table(
        T,
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("biz_type", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("template_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("success_rows", sa.Integer(), nullable=False),
        sa.Column("failed_rows", sa.Integer(), nullable=False),
        sa.Column("error_file_key", sa.String(length=255), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column("operator_name", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("confirm_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.String(length=500), nullable=True),
        *_common_cols(),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    for ix in ("tenant_id", "module_key", "biz_type", "status"):
        op.create_index(f"ix_{T}_{ix}", T, [ix])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, T):
        for idx in inspect(bind).get_indexes(T):
            op.drop_index(idx["name"], table_name=T)
        op.drop_table(T)
