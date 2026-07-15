"""消息通知分类偏好：建表 t_notification_preference（按人+分类开关，聚合读取时真实生效）。

全新业务表，downgrade drop。幂等：inspect 判表。

Revision ID: 0083_notification_preference
Revises: 0082_affairs_psy_survey
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0083_notification_preference"
down_revision = "0082_affairs_psy_survey"
branch_labels = None
depends_on = None

TABLE = "t_notification_preference"


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
            sa.Column("category", sa.String(30), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "user_key", "category", name="uk_notify_pref"))
        op.create_index("ix_notify_pref_user", TABLE, ["tenant_id", "user_key"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, TABLE):
        op.drop_table(TABLE)
