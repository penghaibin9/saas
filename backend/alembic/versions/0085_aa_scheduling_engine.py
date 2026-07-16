"""自动排课引擎地基：教室双容量/专用标记 + 课表项教室外键与来源标记。

对标商业教务系统（强智《智慧教学服务平台操作手册》印刷页 64-68 教室信息、
印刷页 186-188 排课参数、印刷页 213 课表冲突检查 7 类）的排课前置数据模型。
本迁移只加列不改列，全部可空或带 server_default，历史数据零影响：

- t_aa_classroom.exam_seats     考试座位数（考务编排依据，需隔座故通常 < capacity；空则回退 capacity）
- t_aa_classroom.is_exclusive   专用教室（自动排课跳过，仅人工可指定），默认 0 与既有行为一致
- t_aa_schedule_item.classroom_id  教室字典外键（容量/类型校验依据），核销原 model 注释
                                   「classroom_id 外键化留 backlog」；classroom_text 保留为显示快照
- t_aa_schedule_item.source     MANUAL/IMPORT/AUTO 来源标记，默认 MANUAL 与既有行为一致；
                                自动排课重排时据此只清 AUTO 项，绝不动人工排课成果
- t_aa_teaching_task.required_room_type  教室类型要求（空=不限），自动排课选型依据
- t_aa_teaching_task.no_auto_schedule    不参与自动排课，默认 0 与既有行为一致；
                                         职校顶岗实习/集中实训等不进课表网格的课程用它排除，
                                         避免被误判为漏排

回滚：downgrade 逐列 drop，不丢既有课表数据（被 drop 的都是本迁移新增列）。
幂等：inspect 判列存在。

Revision ID: 0085_aa_scheduling_engine
Revises: 0084_user_preference
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0085_aa_scheduling_engine"
down_revision = "0084_user_preference"
branch_labels = None
depends_on = None

T_ROOM = "t_aa_classroom"
T_ITEM = "t_aa_schedule_item"
T_TASK = "t_aa_teaching_task"


def _cols(bind, table):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    room = _cols(bind, T_ROOM)
    if room:
        if "exam_seats" not in room:
            op.add_column(T_ROOM, sa.Column("exam_seats", sa.Integer(), nullable=True,
                                            comment="考试座位数(考务编排依据;空则回退 capacity)"))
        if "is_exclusive" not in room:
            op.add_column(T_ROOM, sa.Column("is_exclusive", sa.Boolean(), nullable=False,
                                            server_default=sa.text("0"),
                                            comment="专用教室(自动排课跳过,仅人工可指定)"))

    item = _cols(bind, T_ITEM)
    if item:
        if "classroom_id" not in item:
            op.add_column(T_ITEM, sa.Column("classroom_id", sa.BigInteger(), nullable=True,
                                            comment="→ t_aa_classroom 教室字典(容量/类型校验依据)"))
            op.create_index("ix_aa_sched_item_room", T_ITEM, ["classroom_id"])
        if "source" not in item:
            op.add_column(T_ITEM, sa.Column("source", sa.String(20), nullable=False,
                                            server_default="MANUAL",
                                            comment="MANUAL/IMPORT/AUTO 排课来源"))
            op.create_index("ix_aa_sched_item_source", T_ITEM, ["source"])

    task = _cols(bind, T_TASK)
    if task:
        if "required_room_type" not in task:
            op.add_column(T_TASK, sa.Column("required_room_type", sa.String(30), nullable=True,
                                            comment="教室类型要求(空=不限),自动排课选型依据"))
        if "no_auto_schedule" not in task:
            op.add_column(T_TASK, sa.Column("no_auto_schedule", sa.Boolean(), nullable=False,
                                            server_default=sa.text("0"),
                                            comment="不参与自动排课(顶岗实习/集中实训等)"))


def downgrade() -> None:
    bind = op.get_bind()

    task = _cols(bind, T_TASK)
    if "no_auto_schedule" in task:
        op.drop_column(T_TASK, "no_auto_schedule")
    if "required_room_type" in task:
        op.drop_column(T_TASK, "required_room_type")

    item = _cols(bind, T_ITEM)
    if "source" in item:
        op.drop_index("ix_aa_sched_item_source", T_ITEM)
        op.drop_column(T_ITEM, "source")
    if "classroom_id" in item:
        op.drop_index("ix_aa_sched_item_room", T_ITEM)
        op.drop_column(T_ITEM, "classroom_id")

    room = _cols(bind, T_ROOM)
    if "is_exclusive" in room:
        op.drop_column(T_ROOM, "is_exclusive")
    if "exam_seats" in room:
        op.drop_column(T_ROOM, "exam_seats")
