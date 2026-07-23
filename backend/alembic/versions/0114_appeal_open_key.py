"""奖助申诉/困难异议：open_key 唯一约束 + 公示拦截配套列

Revision ID: 0114_appeal_open_key
Revises: 0113_funding_appeal
Create Date: 2026-07-23

SUBMITTED 时 open_key=业务主键，CLOSED 清空；MySQL UNIQUE 允许多 NULL，实现「进行中唯一」。
幂等：列/索引已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0114_appeal_open_key"
down_revision = "0113_funding_appeal"
branch_labels = None
depends_on = None


def _cols(bind, table) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns(table)} if table in inspect(bind).get_table_names() else set()


def _indexes(bind, table) -> set[str]:
    return {i["name"] for i in inspect(bind).get_indexes(table)} if table in inspect(bind).get_table_names() else set()


def upgrade() -> None:
    bind = op.get_bind()
    # funding appeal
    if "open_key" not in _cols(bind, "t_affairs_funding_appeal"):
        op.add_column("t_affairs_funding_appeal", sa.Column("open_key", sa.BigInteger(), nullable=True))
        bind.execute(text(
            "UPDATE t_affairs_funding_appeal SET open_key = application_id "
            "WHERE status = 'SUBMITTED' AND (is_deleted = 0 OR is_deleted IS NULL)"
        ))
    if "uk_funding_appeal_open" not in _indexes(bind, "t_affairs_funding_appeal"):
        op.create_index("uk_funding_appeal_open", "t_affairs_funding_appeal",
                        ["tenant_id", "open_key"], unique=True)

    # aid objection
    if "open_key" not in _cols(bind, "t_affairs_aid_objection"):
        op.add_column("t_affairs_aid_objection", sa.Column("open_key", sa.BigInteger(), nullable=True))
        bind.execute(text(
            "UPDATE t_affairs_aid_objection SET open_key = apply_id "
            "WHERE status = 'SUBMITTED' AND (is_deleted = 0 OR is_deleted IS NULL)"
        ))
    if "uk_aid_objection_open" not in _indexes(bind, "t_affairs_aid_objection"):
        op.create_index("uk_aid_objection_open", "t_affairs_aid_objection",
                        ["tenant_id", "open_key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if "uk_funding_appeal_open" in _indexes(bind, "t_affairs_funding_appeal"):
        op.drop_index("uk_funding_appeal_open", table_name="t_affairs_funding_appeal")
    if "open_key" in _cols(bind, "t_affairs_funding_appeal"):
        op.drop_column("t_affairs_funding_appeal", "open_key")
    if "uk_aid_objection_open" in _indexes(bind, "t_affairs_aid_objection"):
        op.drop_index("uk_aid_objection_open", table_name="t_affairs_aid_objection")
    if "open_key" in _cols(bind, "t_affairs_aid_objection"):
        op.drop_column("t_affairs_aid_objection", "open_key")
