"""课程库 Tier1 R2（新增课程/课程分类/课程性质/学分学时/课程负责人/课程停用）：
t_aa_course 加列 description / applicable_majors_json / is_all_major。

背景：owner_teacher_id 列在更早的迁移中已建（课程负责人），但 service 从未读写，属代码基线漂移，
本轮在 service 层补齐读写，不需要新迁移。本迁移只新增 3 列：
- description：课程简介（新增课程表单选填，≤500 字）；
- applicable_majors_json：适用专业 majorId 列表 JSON（选填，不与 is_all_major 同时为真）；
- is_all_major：是否全校通用（默认 False）。
nullable / 有默认值，历史行不受影响。幂等：inspect 判列。

Revision ID: aa_course_lib_tier1_r2
Revises: aa_jxrw_tier1_r1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_course_lib_tier1_r2"
down_revision = "aa_jxrw_tier1_r1"
branch_labels = None
depends_on = None

TABLE = "t_aa_course"


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    cols = _cols(bind)
    if "description" not in cols:
        op.add_column(TABLE, sa.Column("description", sa.String(500), nullable=True, comment="课程简介"))
    if "applicable_majors_json" not in cols:
        op.add_column(TABLE, sa.Column("applicable_majors_json", sa.String(1000), nullable=True,
                                       comment="适用专业 major_id 列表 JSON"))
    if "is_all_major" not in cols:
        op.add_column(TABLE, sa.Column("is_all_major", sa.Boolean(), nullable=False,
                                       server_default=sa.false(), comment="是否全校通用"))


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    cols = _cols(bind)
    if "is_all_major" in cols:
        op.drop_column(TABLE, "is_all_major")
    if "applicable_majors_json" in cols:
        op.drop_column(TABLE, "applicable_majors_json")
    if "description" in cols:
        op.drop_column(TABLE, "description")
