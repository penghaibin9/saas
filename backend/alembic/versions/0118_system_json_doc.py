"""系统管理治理 JSON 文档表

Revision ID: 0118_system_json_doc
Revises: 0117_gd_student_eval_guidance_plan
Create Date: 2026-07-23

临时授权 / 接口凭证 / 同步任务 / 模块开关共用轻量 JSON 文档表。
挂在当前毕业设计迁移链末端，避免与 0116/0117 形成双 head。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0118_system_json_doc"
down_revision = "0117_gd_student_eval_guidance_plan"
branch_labels = None
depends_on = None

T = "t_system_json_doc"


def _has(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has(bind, T):
        return
    op.create_table(
        T,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("doc_key", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column("remark", sa.String(500)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "doc_key", name="uk_system_json_doc_tenant_key"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, T):
        op.drop_table(T)
