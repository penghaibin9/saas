"""0121 · FileObject 对象级授权字段

Revision ID: 0121_file_object_acl
Revises: 0120_message_delivery_ops
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0121_file_object_acl"
down_revision = "0120_message_delivery_ops"
branch_labels = None
depends_on = None

TABLE = "t_file_object"


def _cols(bind) -> set[str]:
    if TABLE not in inspect(bind).get_table_names():
        return set()
    return {c["name"] for c in inspect(bind).get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _cols(bind)
    if not cols:
        return
    if "biz_id" not in cols:
        op.add_column(TABLE, sa.Column("biz_id", sa.String(64), nullable=True))
    if "owner_user_id" not in cols:
        op.add_column(TABLE, sa.Column("owner_user_id", sa.BigInteger(), nullable=True))
    if "visibility" not in cols:
        op.add_column(TABLE, sa.Column("visibility", sa.String(30), nullable=False,
                                       server_default="PRIVATE"))
    if "security_level" not in cols:
        op.add_column(TABLE, sa.Column("security_level", sa.String(30), nullable=False,
                                       server_default="NORMAL"))
    # 历史无归属文件保持 PRIVATE：不回填为租户公开
    try:
        op.create_index("ix_t_file_object_biz_id", TABLE, ["biz_id"])
    except Exception:
        pass
    try:
        op.create_index("ix_t_file_object_owner_user_id", TABLE, ["owner_user_id"])
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    cols = _cols(bind)
    for name in ("security_level", "visibility", "owner_user_id", "biz_id"):
        if name in cols:
            op.drop_column(TABLE, name)
