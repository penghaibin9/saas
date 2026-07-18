"""学生主档姓名列加索引（性能 P0）：

t_student_profile.real_name 此前无索引。审批范围过滤、巡访计划、以及各业务域档案在
student_id 尚未回填时的姓名兜底查询都会对万行学生表全表扫描。加普通索引 ix_t_student_profile_real_name
消除全表扫描。纯加索引，无数据结构破坏、无历史数据兼容问题；回滚 drop_index。

Revision ID: 0099_student_realname_index
Revises: a1198e75cb72
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0099_student_realname_index"
down_revision = "a1198e75cb72"
branch_labels = None
depends_on = None

_TABLE = "t_student_profile"
_INDEX = "ix_t_student_profile_real_name"


def _has_index(bind, table: str, name: str) -> bool:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return True  # 表不存在则视为无需处理（防御，不应发生）
    return any(ix.get("name") == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_index(bind, _TABLE, _INDEX):
        op.create_index(_INDEX, _TABLE, ["real_name"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, _TABLE, _INDEX):
        op.drop_index(_INDEX, table_name=_TABLE)
