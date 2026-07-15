"""学院专业班级 Tier1 续工 R2：新建 t_aa_major_direction（专业方向）+
t_aa_class_adjustment_request（班级调整申请单，合班/拆班/停用/毕业清班批量组织调整）。

背景：13B-学院专业班级二级模块续工（06 专业方向 / 07 班级学生 / 08 班级调整 三个三级模块）。
07 班级学生为只读增强（复用既有 t_student_profile，无迁移）。06/08 为全新业务表，downgrade drop。
幂等：inspect 判表。

Revision ID: aa_orgs_tier1_r2
Revises: aa_jxrw_tier1_r1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_orgs_tier1_r2"
down_revision = "aa_jxrw_tier1_r1"
branch_labels = None
depends_on = None

T_DIRECTION = "t_aa_major_direction"
T_ADJUSTMENT = "t_aa_class_adjustment_request"


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, T_DIRECTION):
        op.create_table(
            T_DIRECTION,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("major_id", sa.BigInteger(), nullable=False),
            sa.Column("direction_name", sa.String(200), nullable=False),
            sa.Column("code", sa.String(50)),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "major_id", "code", name="uk_aa_major_direction_code"))
        op.create_index("ix_aa_major_direction_tenant", T_DIRECTION, ["tenant_id"])
        op.create_index("ix_aa_major_direction_major", T_DIRECTION, ["major_id"])
        op.create_index("ix_aa_major_direction_status", T_DIRECTION, ["status"])

    if not _has(bind, T_ADJUSTMENT):
        op.create_table(
            T_ADJUSTMENT,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("adjust_type", sa.String(20), nullable=False),
            sa.Column("from_class_ids", sa.String(500), nullable=False),
            sa.Column("to_class_id", sa.BigInteger()),
            sa.Column("reason", sa.String(1000), nullable=False),
            sa.Column("check_result_json", sa.String(2000)),
            sa.Column("checked_at", sa.DateTime()),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        op.create_index("ix_aa_class_adjust_req_tenant", T_ADJUSTMENT, ["tenant_id"])
        op.create_index("ix_aa_class_adjust_req_type", T_ADJUSTMENT, ["adjust_type"])
        op.create_index("ix_aa_class_adjust_req_status", T_ADJUSTMENT, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, T_ADJUSTMENT):
        op.drop_table(T_ADJUSTMENT)
    if _has(bind, T_DIRECTION):
        op.drop_table(T_DIRECTION)
