"""批次A：监考/巡考教师时间线互斥锁 + 考场 canonical classroomId。

监考冲突检测原来是"查该教师全部已排场次→比对时段→通过则插入"，不是原子操作：两个并发
请求都查到"无冲突"再各自插入，同一个老师就被排进两场同时段的考试。本迁移新增
t_aa_exam_teacher_lock 作为纯锁行，写监考/巡考前先取锁再做冲突检测+插入。

顺带给 t_aa_exam_room 加 classroom_id 上的索引（发布门禁按 canonical classroomId 扫描
跨批次教室冲突，人工建考场现在也可以直接传 classroomId 而不是只靠文本模糊匹配）。

Revision ID: 20260807_aa_exam_tlock
Revises: 20260807_aa_snap_cols
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260807_aa_exam_tlock"
down_revision = "20260807_aa_snap_cols"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_LOCK = "t_aa_exam_teacher_lock"
_ROOM = "t_aa_exam_room"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _has_index(bind, table: str, name: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(ix["name"] == name for ix in inspect(bind).get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, _LOCK):
        op.create_table(
            _LOCK,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("teacher_key", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "teacher_key", name="uk_aa_exam_teacher_lock"),
        )
        op.create_index("ix_aa_exam_teacher_lock_key", _LOCK, ["teacher_key"])

    if _has_table(bind, _ROOM) and not _has_index(bind, _ROOM, "ix_aa_exam_room_classroom"):
        op.create_index("ix_aa_exam_room_classroom", _ROOM, ["classroom_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, _ROOM, "ix_aa_exam_room_classroom"):
        op.drop_index("ix_aa_exam_room_classroom", table_name=_ROOM)
    if _has_table(bind, _LOCK):
        op.drop_table(_LOCK)
