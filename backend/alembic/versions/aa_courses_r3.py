"""课程库 Tier1 R3（课程材料/课程大纲）：新建 t_aa_course_material。

背景：W3 课程库交付 9 页时未覆盖「课程大纲/考核方式/课程材料/课程归档」4 个三级菜单（施工记录续工第三轮）。
核实结论：
- 考核方式 = 已有 t_aa_course.exam_mode 字段（EXAM/CHECK），只是控制台未开放对应 Tab，本迁移不涉及；
- 课程归档 = 由已有 version/prev_version_id/status 字段派生只读视图（已停用 + 被新版本取代的历史版本），
  控制台新增 Tab 纯前端计算，本迁移不涉及；
- 课程大纲/课程材料 = 确无现有实现，新建本表承接（design source：
  《13B-教务中心全业务流程设计总册》§4.7A 教学资源 V1 轻量路径——挂 course_id、复用现有 t_file_object
  文件中心、不强制挂教学任务、不做完整 DRAFT/SUBMITTED/SHARED/ARCHIVED 审核流转）。

t_aa_course_material：课程材料/大纲清单，附件字节仍走 t_file_object（file_service 真实上传），
本表只登记 (course_id, file_id) 回链 + 材料类型 + 上传人。软删（status=VOIDED + is_deleted）留痕。
全部含 tenant_id 行级隔离 + CommonMixin（软删/审计/乐观锁）。幂等：inspect 检测已存在则跳过。

Revision ID: aa_courses_r3
Revises: aa_course_lib_tier1_r2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_courses_r3"
down_revision = "aa_course_lib_tier1_r2"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
MATERIAL = "t_aa_course_material"


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
    if not _has(bind, MATERIAL):
        op.create_table(MATERIAL, *_common(
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
            sa.Column("course_id", sa.BigInteger(), nullable=False, comment="回链 t_aa_course.id"),
            sa.Column("material_type", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("file_id", sa.String(length=100), nullable=True),
            sa.Column("file_name", sa.String(length=255), nullable=True),
            sa.Column("remark", sa.String(length=500), nullable=True),
            sa.Column("uploader", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
        ))
        op.create_index("ix_t_aa_course_material_tenant_id", MATERIAL, ["tenant_id"])
        op.create_index("ix_t_aa_course_material_course_id", MATERIAL, ["course_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, MATERIAL):
        for idx in inspect(bind).get_indexes(MATERIAL):
            op.drop_index(idx["name"], table_name=MATERIAL)
        op.drop_table(MATERIAL)
