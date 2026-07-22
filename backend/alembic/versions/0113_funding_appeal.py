"""奖助公示申诉表 t_affairs_funding_appeal

Revision ID: 0113_funding_appeal
Revises: 0112_system_editable_config
Create Date: 2026-07-23

对齐困难认定异议：公示期可申诉，复核成立则驳回申请。
幂等：表已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0113_funding_appeal"
down_revision = "0112_system_editable_config"
branch_labels = None
depends_on = None

T = "t_affairs_funding_appeal"


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
        sa.Column("application_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("student_id", sa.BigInteger(), index=True),
        sa.Column("appellant_name", sa.String(100)),
        sa.Column("reason", sa.String(1000)),
        sa.Column("status", sa.String(30), nullable=False, server_default="SUBMITTED", index=True),
        sa.Column("result", sa.String(30)),
        sa.Column("review_opinion", sa.String(1000)),
        sa.Column("reviewer", sa.String(100)),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, T):
        op.drop_table(T)
