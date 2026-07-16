"""通用用户偏好：建表 t_user_preference（按人 + 偏好键的 KV）。

首个用途是新手引导「已看过」标记，存后端而非 localStorage，保证换设备/清缓存不重复弹。
全新业务表，无历史数据兼容问题；downgrade drop。幂等：inspect 判表。

Revision ID: 0084_user_preference
Revises: aa_jxrw_tier1_r1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0084_user_preference"
down_revision = "aa_jxrw_tier1_r1"
branch_labels = None
depends_on = None

TABLE = "t_user_preference"


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("user_key", sa.String(100), nullable=False),
            sa.Column("pref_key", sa.String(100), nullable=False),
            sa.Column("pref_value", sa.String(500), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "user_key", "pref_key", name="uk_user_pref"))
        op.create_index("ix_user_pref_user", TABLE, ["tenant_id", "user_key"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, TABLE):
        op.drop_table(TABLE)
