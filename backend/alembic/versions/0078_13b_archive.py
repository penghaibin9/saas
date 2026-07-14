"""13B-R7 教务归档：建 2 表（归档批次 + 9数据域物料）。

t_aa_archive_batch  归档批次（一学期一批次）
t_aa_archive_item   归档物料（9 数据域完整性）

全新业务表，downgrade 逆序 drop。幂等：inspect 判表存在再建/删。

Revision ID: 0078_13b_archive
Revises: 0077_13b_evaluation
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0078_13b_archive"
down_revision = "0077_13b_evaluation"
branch_labels = None
depends_on = None

_COMMON = [
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("created_by", sa.BigInteger()),
    sa.Column("updated_by", sa.BigInteger()),
    sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
]


def _pk_tenant():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
    ]


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, "t_aa_archive_batch"):
        op.create_table(
            "t_aa_archive_batch", *_pk_tenant(),
            sa.Column("batch_name", sa.String(200), nullable=False),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("term_code", sa.String(50)),
            sa.Column("checked_at", sa.DateTime()),
            sa.Column("archived_at", sa.DateTime()),
            sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("remark", sa.String(500)),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "term_id", name="uk_aa_archive_batch"))
        op.create_index("ix_aa_archive_batch_status", "t_aa_archive_batch", ["tenant_id", "status"])

    if not _has(bind, "t_aa_archive_item"):
        op.create_table(
            "t_aa_archive_item", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("domain", sa.String(50), nullable=False),
            sa.Column("domain_label", sa.String(100)),
            sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("present", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("remark", sa.String(300)),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "batch_id", "domain", name="uk_aa_archive_item"))
        op.create_index("ix_aa_archive_item_batch", "t_aa_archive_item", ["tenant_id", "batch_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_aa_archive_item", "t_aa_archive_batch"):
        if _has(bind, t):
            op.drop_table(t)
