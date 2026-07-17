"""学生 PC 门户 R2 · 登录验证码表：

新建 1 表：t_portal_login_otp（家长验证码登录 OTP；code 只存 hash；consumed/attempts 限次；
expires_at 限时）。全新表，无历史数据兼容问题。回滚 drop_table。

Revision ID: portal_r2_login_otp
Revises: portal_r1_parent_link
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "portal_r2_login_otp"
down_revision = "portal_r1_parent_link"
branch_labels = None
depends_on = None


def _has_table(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "t_portal_login_otp"):
        return
    op.create_table(
        "t_portal_login_otp",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("phone_hash", sa.String(length=128), nullable=False, index=True),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False, server_default="GUARDIAN_LOGIN"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "t_portal_login_otp"):
        op.drop_table("t_portal_login_otp")
