"""岗位实习中心: 实习协议模板库 t_internship_agreement_template

Revision ID: 0016_internship_agreement_template
Revises: 0015_excel_import_job
Create Date: 2026-07-07

协议模板配置主数据。幂等：inspect 已存在则跳过。JSON 适用范围 + 4 态状态机 + 默认标记。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0016_internship_agreement_template"
down_revision = "0015_excel_import_job"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
T = "t_internship_agreement_template"


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
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("template_version", sa.String(length=32), nullable=False),
        sa.Column("scope_college_ids", sa.JSON(), nullable=True),
        sa.Column("scope_major_ids", sa.JSON(), nullable=True),
        sa.Column("scope_grades", sa.JSON(), nullable=True),
        sa.Column("scope_batch_ids", sa.JSON(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("variables", sa.JSON(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.String(length=500), nullable=True),
        sa.Column("enabled_at", sa.DateTime(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("archived_by", sa.String(length=100), nullable=True),
        *_common_cols(),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    for ix in ("tenant_id", "status"):
        op.create_index(f"ix_{T}_{ix}", T, [ix])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, T):
        for idx in inspect(bind).get_indexes(T):
            op.drop_index(idx["name"], table_name=T)
        op.drop_table(T)
