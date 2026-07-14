"""13A-C 奖助发放台账：t_affairs_funding_disbursement

Revision ID: 0058_13a_funding_disbursement
Revises: 0057_13a_league_dev
Create Date: 2026-07-14

单表新增；GRANTED 申请 1:1 生成发放记录。金额脱敏、不落银行卡全号(仅后4位)。
幂等：表已存在则跳过。回滚：downgrade drop（无历史数据零风险）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0058_13a_funding_disbursement"
down_revision = "0057_13a_league_dev"
branch_labels = None
depends_on = None

T = "t_affairs_funding_disbursement"


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
            sa.Column("application_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("project_type", sa.String(length=50)),
            sa.Column("amount", sa.Numeric(precision=12, scale=2)),
            sa.Column("disburse_no", sa.String(length=100)),
            sa.Column("bank_last4", sa.String(length=10)),
            sa.Column("bank_status", sa.String(length=30), nullable=False, server_default="PENDING", index=True),
            sa.Column("issued_at", sa.DateTime()),
            sa.Column("fail_reason", sa.String(length=500)),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "application_id", name="uk_funding_disbursement_app"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    if _has(bind, T):
        op.drop_table(T)
