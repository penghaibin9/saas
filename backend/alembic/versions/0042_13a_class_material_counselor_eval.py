"""13A-B2: 班级材料 + 辅导员考评（建 3 张表）

Revision ID: 0042_13a_class_material_counselor_eval
Revises: 0041_internship_plan_task_progress
Create Date: 2026-07-11

说明：班级与辅导员模块 greenfield 表。
- t_affairs_class_material：班级台账材料（附件存 file_id 回链 t_file_object）。
- t_affairs_counselor_assessment_period / t_affairs_counselor_assessment：辅导员考评周期 + 记录。
全部含 tenant_id 行级隔离 + CommonMixin（软删/审计/乐观锁）。幂等：inspect 检测已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0042_13a_class_material_counselor_eval"
down_revision = "0041_internship_plan_task_progress"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
MATERIAL = "t_affairs_class_material"
PERIOD = "t_affairs_counselor_assessment_period"
ASSESS = "t_affairs_counselor_assessment"


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

    # 1) 班级材料
    if not _has(bind, MATERIAL):
        op.create_table(MATERIAL, *_common(
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
            sa.Column("class_id", sa.BigInteger(), nullable=False),
            sa.Column("material_type", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("file_id", sa.String(length=100), nullable=True),
            sa.Column("file_name", sa.String(length=255), nullable=True),
            sa.Column("material_at", sa.DateTime(), nullable=True),
            sa.Column("remark", sa.String(length=500), nullable=True),
            sa.Column("uploader", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
        ))
        op.create_index("ix_t_affairs_class_material_tenant_id", MATERIAL, ["tenant_id"])
        op.create_index("ix_t_affairs_class_material_class_id", MATERIAL, ["class_id"])

    # 2) 辅导员考评周期
    if not _has(bind, PERIOD):
        op.create_table(PERIOD, *_common(
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
            sa.Column("period_name", sa.String(length=100), nullable=False),
            sa.Column("semester", sa.String(length=50), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("remark", sa.String(length=500), nullable=True),
        ))
        op.create_index("ix_t_affairs_counselor_assessment_period_tenant_id", PERIOD, ["tenant_id"])

    # 3) 辅导员考评记录
    if not _has(bind, ASSESS):
        op.create_table(ASSESS, *_common(
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
            sa.Column("period_id", sa.BigInteger(), nullable=False),
            sa.Column("counselor_id", sa.BigInteger(), nullable=True),
            sa.Column("counselor_name", sa.String(length=100), nullable=True),
            sa.Column("class_count", sa.Integer(), nullable=False),
            sa.Column("student_count", sa.Integer(), nullable=False),
            sa.Column("metrics_json", sa.Text(), nullable=True),
            sa.Column("auto_score", sa.Numeric(6, 1), nullable=True),
            sa.Column("college_score", sa.Numeric(6, 1), nullable=True),
            sa.Column("total_score", sa.Numeric(6, 1), nullable=True),
            sa.Column("rank_no", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("scored_by", sa.String(length=100), nullable=True),
            sa.Column("scored_at", sa.DateTime(), nullable=True),
        ))
        op.create_index("ix_t_affairs_counselor_assessment_tenant_id", ASSESS, ["tenant_id"])
        op.create_index("ix_t_affairs_counselor_assessment_period_id", ASSESS, ["period_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in (ASSESS, PERIOD, MATERIAL):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
