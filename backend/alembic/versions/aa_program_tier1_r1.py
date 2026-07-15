"""培养方案 Tier1 补建：t_aa_program_graduation_requirement（毕业要求结构化条目）。

背景：13B-培养方案二级模块续工（方案制定/方案版本/课程模块/学分要求/毕业要求/方案审核/方案发布 7 个
三级模块）。学分结构复用既有 t_aa_program.requirement_json；毕业要求需要独立可增删改的结构化条目
（知识/能力/素质/职业证书分类），故新建本表。全新业务表，downgrade drop。幂等：inspect 判表。

Revision ID: aa_program_tier1_r1
Revises: 0083_notification_preference
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_program_tier1_r1"
down_revision = "0083_notification_preference"
branch_labels = None
depends_on = None

TABLE = "t_aa_program_graduation_requirement"


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("program_id", sa.BigInteger(), nullable=False),
            sa.Column("category", sa.String(50), nullable=False, server_default="ABILITY"),
            sa.Column("content", sa.String(1000), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        op.create_index("ix_aa_program_grad_req_tenant", TABLE, ["tenant_id"])
        op.create_index("ix_aa_program_grad_req_program", TABLE, ["program_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, TABLE):
        op.drop_table(TABLE)
