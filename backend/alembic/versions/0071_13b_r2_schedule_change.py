"""13B-R2 调停课：t_aa_schedule_change（SM-08 调课/停课/补课）+ t_aa_schedule_item.change_id 变更标记回链。

Revision ID: 0071_13b_r2_schedule_change
Revises: 0068_13b_r1_grade_review
Create Date: 2026-07-14

说明：教师就已发布课表项发起调停课，审批链学院审→教务处审，终审通过后系统改写课表——原课位标 CHANGED
保留历史，调课/补课生成新课表项并回链本单(new_item_id + schedule_item.change_id)。
并行基线：本模块与 R1/R3+ 各模块 down_revision 均指向 0068_13b_r1_grade_review，由总控合并阶段串成单链。
幂等：表已存在则跳过；change_id 列已存在则跳过。回滚：downgrade 删列 + drop 本表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0071_13b_r2_schedule_change"
down_revision = "0070_13b_r4_classroom"
branch_labels = None
depends_on = None

TABLE = "t_aa_schedule_change"
ITEM_TABLE = "t_aa_schedule_item"


def _has_table(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def _has_column(bind, table, column) -> bool:
    if not _has_table(bind, table):
        return False
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # 1) 课表项新增 change_id（变更标记 / 回链调停课单）—— 幂等加列
    if _has_table(bind, ITEM_TABLE) and not _has_column(bind, ITEM_TABLE, "change_id"):
        op.add_column(ITEM_TABLE, sa.Column("change_id", sa.BigInteger(), nullable=True,
                                            comment="→ t_aa_schedule_change 生成本项的调停课单；null=原始排课"))
        op.create_index("ix_aa_schedule_item_change", ITEM_TABLE, ["change_id"])

    # 2) 调停课单表
    if _has_table(bind, TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("term_id", sa.BigInteger()),
        sa.Column("batch_id", sa.BigInteger()),
        sa.Column("origin_item_id", sa.BigInteger()),
        sa.Column("task_id", sa.BigInteger()),
        sa.Column("change_type", sa.String(length=20), nullable=False, comment="ADJUST/STOP/MAKEUP"),
        sa.Column("course_name", sa.String(length=200)),
        sa.Column("class_id", sa.BigInteger()),
        sa.Column("class_name", sa.String(length=100)),
        sa.Column("teacher_key", sa.String(length=100)),
        sa.Column("teacher_name", sa.String(length=100)),
        sa.Column("origin_weekday", sa.Integer()),
        sa.Column("origin_slot_no", sa.Integer()),
        sa.Column("origin_start_week", sa.Integer()),
        sa.Column("origin_end_week", sa.Integer()),
        sa.Column("origin_week_parity", sa.String(length=10)),
        sa.Column("origin_classroom", sa.String(length=100)),
        sa.Column("target_weekday", sa.Integer()),
        sa.Column("target_slot_no", sa.Integer()),
        sa.Column("target_start_week", sa.Integer()),
        sa.Column("target_end_week", sa.Integer()),
        sa.Column("target_week_parity", sa.String(length=10)),
        sa.Column("target_classroom", sa.String(length=100)),
        sa.Column("makeup_plan", sa.String(length=500)),
        sa.Column("reason", sa.String(length=500)),
        sa.Column("new_item_id", sa.BigInteger()),
        sa.Column("applied_at", sa.DateTime()),
        sa.Column("applicant_id", sa.BigInteger()),
        sa.Column("current_node", sa.String(length=50)),
        sa.Column("workflow_instance_id", sa.BigInteger()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="SUBMITTED",
                  comment="SUBMITTED/COLLEGE_REVIEW/ACADEMIC_REVIEW/APPROVED/REJECTED/CANCELLED/APPLIED"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_aa_schedule_change_tenant_status", TABLE, ["tenant_id", "status"])
    op.create_index("ix_aa_schedule_change_teacher", TABLE, ["tenant_id", "teacher_key"])
    op.create_index("ix_aa_schedule_change_term", TABLE, ["tenant_id", "term_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, TABLE):
        op.drop_table(TABLE)
    if _has_column(bind, ITEM_TABLE, "change_id"):
        try:
            op.drop_index("ix_aa_schedule_item_change", table_name=ITEM_TABLE)
        except Exception:  # noqa: BLE001
            pass
        op.drop_column(ITEM_TABLE, "change_id")
