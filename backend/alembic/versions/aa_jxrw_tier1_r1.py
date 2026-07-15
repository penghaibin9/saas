"""教学任务 Tier1 续工：t_aa_teaching_task 加列 merged_into_id / merge_snapshot_json（合班拆班溯源）。

合班：多条同批次同课程教学任务合并为一条（survivor），其余行 status=MERGED 且 merged_into_id 指向
survivor；survivor.merge_snapshot_json 记录合并前自身快照，供拆班精确还原。nullable，历史行不受影响。
幂等：inspect 判列。

Revision ID: aa_jxrw_tier1_r1
Revises: 0083_notification_preference
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_jxrw_tier1_r1"
down_revision = "0083_notification_preference"
branch_labels = None
depends_on = None

TABLE = "t_aa_teaching_task"


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def _idx(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {i["name"] for i in insp.get_indexes(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    cols = _cols(bind)
    if "merged_into_id" not in cols:
        op.add_column(TABLE, sa.Column("merged_into_id", sa.BigInteger(), nullable=True,
                                       comment="合班后本行被并入的 survivor 教学任务 id（本行 status=MERGED 时有效）"))
    if "merge_snapshot_json" not in cols:
        op.add_column(TABLE, sa.Column("merge_snapshot_json", sa.String(1000), nullable=True,
                                       comment="合班快照（survivor 合并前自身字段 + 成员 taskId 列表），供拆班还原"))
    if "ix_t_aa_teaching_task_merged_into_id" not in _idx(bind):
        op.create_index("ix_t_aa_teaching_task_merged_into_id", TABLE, ["merged_into_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    if "ix_t_aa_teaching_task_merged_into_id" in _idx(bind):
        op.drop_index("ix_t_aa_teaching_task_merged_into_id", table_name=TABLE)
    cols = _cols(bind)
    if "merge_snapshot_json" in cols:
        op.drop_column(TABLE, "merge_snapshot_json")
    if "merged_into_id" in cols:
        op.drop_column(TABLE, "merged_into_id")
