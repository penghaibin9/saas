"""13A-D 第二课堂积分申诉：t_affairs_credit_appeal

Revision ID: 0061_13a_credit_appeal
Revises: 0060_13a_aid_objection
Create Date: 2026-07-14

单表新增；缺记/记错申诉→通过(补记/调整学分)/驳回。幂等：表已存在则跳过。回滚：drop。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0061_13a_credit_appeal"
down_revision = "0060_13a_aid_objection"
branch_labels = None
depends_on = None

T = "t_affairs_credit_appeal"


def _has(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def _common_cols():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade():
    bind = op.get_bind()
    if not _has(bind, T):
        op.create_table(
            T,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("activity_id", sa.BigInteger(), index=True),
            sa.Column("appeal_type", sa.String(length=20), nullable=False, server_default="MISSING"),
            sa.Column("claim_credit_type", sa.String(length=30), nullable=False, server_default="SECOND_CLASS"),
            sa.Column("claim_value", sa.Numeric(precision=6, scale=2)),
            sa.Column("reason", sa.String(length=1000)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="SUBMITTED", index=True),
            sa.Column("result_credit_id", sa.BigInteger()),
            sa.Column("review_opinion", sa.String(length=1000)),
            sa.Column("reviewer", sa.String(length=100)),
            sa.Column("reviewed_at", sa.DateTime()),
            *_common_cols(),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    if _has(bind, T):
        op.drop_table(T)
