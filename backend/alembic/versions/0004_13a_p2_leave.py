"""13A-P2: t_cs_leave 加 8 列 + 建 t_affairs_leave_cancel_record / t_affairs_leave_extension

Revision ID: 0004_13a_p2_leave
Revises: 0003_13a_p1_class_cadre
Create Date: 2026-07-06

说明：请假闭环范式。加列全 nullable（双状态列并行，不动既有列语义，P0 §4.2 集成①）；
两张子表回链 t_cs_leave.id。存量库 backfill 走 backend/scripts/_backfill_cs_leave_affairs_status.py
（DDL 与数据迁移分离，C3 §5.6）。幂等：inspect 检测已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0004_13a_p2_leave"
down_revision = "0003_13a_p1_class_cadre"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
LEAVE = "t_cs_leave"
CANCEL = "t_affairs_leave_cancel_record"
EXT = "t_affairs_leave_extension"

_NEW_COLS = [
    ("student_id", sa.BigInteger()),
    ("affairs_status", sa.String(length=50)),
    ("days", sa.Numeric(5, 1)),
    ("workflow_instance_id", sa.BigInteger()),
    ("expected_return_at", sa.DateTime()),
    ("actual_return_at", sa.DateTime()),
    ("parent_notify", sa.Boolean()),
    ("overdue_pushed_at", sa.DateTime()),
]


def _cols(bind, table):
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _has(bind, table):
    return table in inspect(bind).get_table_names()


def _common(*extra):
    return [
        *extra,
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    # 1) t_cs_leave 加 8 列（全 nullable）
    existing = _cols(bind, LEAVE)
    for name, coltype in _NEW_COLS:
        if name not in existing:
            op.add_column(LEAVE, sa.Column(name, coltype, nullable=True))
    cur_idx = {i["name"] for i in inspect(bind).get_indexes(LEAVE)}
    for ix, col in (("ix_t_cs_leave_affairs_status", "affairs_status"),
                    ("ix_t_cs_leave_student_id", "student_id"),
                    ("ix_t_cs_leave_workflow_instance_id", "workflow_instance_id")):
        if ix not in cur_idx:
            op.create_index(ix, LEAVE, [col])

    # 2) 销假记录
    if not _has(bind, CANCEL):
        op.create_table(CANCEL, *_common(
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("leave_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=True),
            sa.Column("actual_return_at", sa.DateTime(), nullable=True),
            sa.Column("proof_note", sa.String(length=500), nullable=True),
            sa.Column("confirm_by", sa.String(length=100), nullable=True),
            sa.Column("confirm_at", sa.DateTime(), nullable=True),
            sa.Column("confirm_note", sa.String(length=500), nullable=True),
            sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
        ))
        op.create_index("ix_t_affairs_leave_cancel_record_tenant_id", CANCEL, ["tenant_id"])
        op.create_index("ix_t_affairs_leave_cancel_record_leave_id", CANCEL, ["leave_id"])

    # 3) 续假申请
    if not _has(bind, EXT):
        op.create_table(EXT, *_common(
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("leave_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=True),
            sa.Column("old_end_time", sa.DateTime(), nullable=True),
            sa.Column("new_end_time", sa.DateTime(), nullable=True),
            sa.Column("extend_days", sa.Numeric(5, 1), nullable=True),
            sa.Column("reason", sa.String(length=500), nullable=True),
            sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
        ))
        op.create_index("ix_t_affairs_leave_extension_tenant_id", EXT, ["tenant_id"])
        op.create_index("ix_t_affairs_leave_extension_leave_id", EXT, ["leave_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in (EXT, CANCEL):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
    if _has(bind, LEAVE):
        cols = _cols(bind, LEAVE)
        to_drop = [name for name, _ in _NEW_COLS if name in cols]
        if to_drop:
            # 先删所有引用待删列的索引（含 model index=True 由 create_all 自动建的），
            # 否则 SQLite 删列时索引悬挂报错。
            for idx in inspect(bind).get_indexes(LEAVE):
                if set(idx.get("column_names") or []) & set(to_drop):
                    op.drop_index(idx["name"], table_name=LEAVE)
            # batch 模式：SQLite 通过 copy-recreate 安全删列
            with op.batch_alter_table(LEAVE) as batch:
                for name in to_drop:
                    batch.drop_column(name)
