"""13A-D 辅导员考评：t_affairs_counselor_eval_indicator / t_affairs_counselor_eval

Revision ID: 0062_13a_counselor_eval
Revises: 0061_13a_credit_appeal
Create Date: 2026-07-14

两表新增。幂等：表已存在则跳过。回滚：逆序 drop。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0062_13a_counselor_eval"
down_revision = "0061_13a_credit_appeal"
branch_labels = None
depends_on = None

T_IND = "t_affairs_counselor_eval_indicator"
T_EVAL = "t_affairs_counselor_eval"


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
    if not _has(bind, T_IND):
        op.create_table(
            T_IND,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=50)),
            sa.Column("weight", sa.Numeric(precision=6, scale=2)),
            sa.Column("max_score", sa.Numeric(precision=6, scale=2), server_default="100"),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ENABLED", index=True),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "name", name="uk_counselor_indicator_name"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    if not _has(bind, T_EVAL):
        op.create_table(
            T_EVAL,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("period_code", sa.String(length=50), nullable=False, index=True),
            sa.Column("counselor_key", sa.String(length=100), nullable=False),
            sa.Column("counselor_name", sa.String(length=100)),
            sa.Column("scores_json", sa.JSON()),
            sa.Column("total_score", sa.Numeric(precision=8, scale=2)),
            sa.Column("remark", sa.String(length=1000)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT", index=True),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("appeal_status", sa.String(length=30), nullable=False, server_default="NONE", index=True),
            sa.Column("appeal_reason", sa.String(length=1000)),
            sa.Column("appeal_result", sa.String(length=30)),
            sa.Column("appeal_opinion", sa.String(length=1000)),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "period_code", "counselor_key", name="uk_counselor_eval_period_key"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    for t in (T_EVAL, T_IND):
        if _has(bind, t):
            op.drop_table(t)
