"""13B-R4 教学资源：t_aa_classroom 教室字典（楼栋/教室/容量/类型/可用状态）

Revision ID: 0070_13b_r4_classroom
Revises: 0068_13b_r1_grade_review
Create Date: 2026-07-14

说明：教室字典最小闭环（方案A）。字典表独立，课表 t_aa_schedule_item.classroom_text 保持自由
文本快照不改列，classroom_id 外键化留 backlog。排课 UI 从本字典选择、容量非阻断 warning。
唯一(tenant,building_code,room_code)。可用状态 AVAILABLE/DISABLED/MAINTENANCE。

并行说明：本卡与 R1(成绩,0068) 等模块并行开发，down_revision 统一指向 0068_13b_r1_grade_review；
总控合并阶段将多头重新串成单链。幂等：表已存在则跳过；测试用 metadata.create_all 不受影响。
回滚：downgrade 直接 drop 本表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0070_13b_r4_classroom"
down_revision = "0069_13b_r3_orgs"
branch_labels = None
depends_on = None

TABLE = "t_aa_classroom"


def _has_table(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("building_code", sa.String(length=50), nullable=False),
        sa.Column("building_name", sa.String(length=100), nullable=False),
        sa.Column("room_code", sa.String(length=50), nullable=False),
        sa.Column("room_name", sa.String(length=100)),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("room_type", sa.String(length=30), nullable=False, server_default="LECTURE"),
        sa.Column("campus_code", sa.String(length=50)),
        sa.Column("remark", sa.String(length=500)),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="AVAILABLE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "building_code", "room_code", name="uk_aa_classroom"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_aa_classroom_tenant", TABLE, ["tenant_id"])
    op.create_index("ix_aa_classroom_building", TABLE, ["building_code"])
    op.create_index("ix_aa_classroom_room", TABLE, ["room_code"])
    op.create_index("ix_aa_classroom_status", TABLE, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, TABLE):
        op.drop_table(TABLE)
