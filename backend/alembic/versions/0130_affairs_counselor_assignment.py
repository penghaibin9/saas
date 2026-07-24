"""新增班级辅导员责任关系，并从历史 counselor_id 回填主责。

Revision ID: 0130_affairs_counselor_assignment
Revises: 0129_gd_stable_mentor_ids
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0130_affairs_counselor_assignment"
down_revision = "0129_gd_stable_mentor_ids"
branch_labels = None
depends_on = None

TABLE = "t_affairs_counselor_assignment"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("class_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("duty_type", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("effective_from", sa.DateTime(), nullable=True),
            sa.Column("effective_to", sa.DateTime(), nullable=True),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("handover_from_user_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_affairs_counselor_assignment_class_status", TABLE,
                        ["tenant_id", "class_id", "status"])
        op.create_index("ix_affairs_counselor_assignment_user_status", TABLE,
                        ["tenant_id", "user_id", "status"])

    # 老班级 counselor_id 为唯一可迁移的历史主责事实；已存在关系则不覆盖。
    insp = inspect(bind)
    if TABLE not in insp.get_table_names() or "t_class" not in insp.get_table_names():
        return
    class_cols = {c["name"] for c in insp.get_columns("t_class")}
    if "counselor_id" not in class_cols:
        return
    now = datetime.utcnow()
    classes = bind.execute(text(
        "SELECT id, tenant_id, counselor_id FROM t_class "
        "WHERE counselor_id IS NOT NULL AND (is_deleted = 0 OR is_deleted IS NULL)"
    )).mappings().all()
    for row in classes:
        exists = bind.execute(text(
            f"SELECT 1 FROM {TABLE} WHERE tenant_id = :tenant_id AND class_id = :class_id "
            "AND duty_type = 'PRIMARY' AND status = 'ACTIVE' AND is_deleted = 0 LIMIT 1"
        ), {"tenant_id": row["tenant_id"], "class_id": row["id"]}).first()
        if not exists:
            bind.execute(text(
                f"INSERT INTO {TABLE} "
                "(tenant_id, class_id, user_id, duty_type, status, effective_from, "
                "created_at, updated_at, is_deleted, version) "
                "VALUES (:tenant_id, :class_id, :user_id, 'PRIMARY', 'ACTIVE', :now, "
                ":now, :now, 0, 1)"
            ), {"tenant_id": row["tenant_id"], "class_id": row["id"],
                "user_id": row["counselor_id"], "now": now})


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return
    for name in ("ix_affairs_counselor_assignment_user_status",
                 "ix_affairs_counselor_assignment_class_status"):
        if any(ix.get("name") == name for ix in insp.get_indexes(TABLE)):
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
