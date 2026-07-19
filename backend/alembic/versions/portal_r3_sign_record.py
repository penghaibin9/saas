"""学生 PC 门户 R3 · 电子签署留痕表：

新建 1 表：t_portal_sign_record（可靠留痕：内容 SHA-256 哈希快照 + 时间戳 + 签署人 + provider）。
全新表，无历史数据兼容问题。回滚 drop_table。

Revision ID: portal_r3_sign_record
Revises: portal_r2_login_otp
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "portal_r3_sign_record"
down_revision = "portal_r2_login_otp"
branch_labels = None
depends_on = None


def _has_table(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "t_portal_sign_record"):
        return
    op.create_table(
        "t_portal_sign_record",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("biz_type", sa.String(length=50), nullable=False, index=True),
        sa.Column("biz_id", sa.String(length=64), index=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False, server_default="reliable_log"),
        sa.Column("signer_name", sa.String(length=100)),
        sa.Column("signed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "t_portal_sign_record"):
        op.drop_table("t_portal_sign_record")
