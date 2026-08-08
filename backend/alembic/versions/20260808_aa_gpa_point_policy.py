"""P1-GPA：绩点换算策略版本化 + t_acad_grade 冻结列。

原实现 `_course_point(score)` 是硬编码公式，全租户统一、不可配置，且每次 `_refresh_aggregates`
都用"当前"公式重算全部历史成绩——学校调整绩点口径会静默改写已毕业学生的历史 GPA。

本迁移新增 t_aa_gpa_point_policy（租户级、可版本化，DRAFT/ACTIVE/SUPERSEDED + active_scope_key
唯一索引兜底并发发布，与 t_aa_effective_grade_policy 同一套合同），并给 t_acad_grade 加三列
冻结绩点计算结果（gpa_point/gpa_policy_code/gpa_policy_version）。不做数据回填——历史行冻结列
留 NULL，下次被 `_refresh_aggregates` 触达时按默认策略（与旧公式逐分值等价）惰性冻结一次，
此后不再随策略升级改变，保证升级当天不改变任何学生的已展示 GPA。

Revision ID: 20260808_aa_gpa_policy
Revises: 20260807_aa_exam_tlock
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260808_aa_gpa_policy"
down_revision = "20260807_aa_exam_tlock"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_POLICY = "t_aa_gpa_point_policy"
_GRADE = "t_acad_grade"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _has_column(bind, table: str, name: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(col["name"] == name for col in inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, _POLICY):
        op.create_table(
            _POLICY,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("policy_code", sa.String(80), nullable=False),
            sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("active_scope_key", sa.String(40), nullable=True),
            sa.Column("scale_type", sa.String(20), nullable=False, server_default="LINEAR"),
            sa.Column("linear_fail_score", sa.Integer(), nullable=True),
            sa.Column("linear_anchor_score", sa.Integer(), nullable=True),
            sa.Column("linear_divisor", sa.Integer(), nullable=True),
            sa.Column("bands_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.Column("remark", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "policy_code", "policy_version", name="uk_aa_gpa_policy_ver"),
            sa.UniqueConstraint("tenant_id", "active_scope_key", name="uk_aa_gpa_policy_scope"),
        )
        op.create_index("ix_aa_gpa_policy_active", _POLICY, ["tenant_id", "status"])

    if _has_table(bind, _GRADE):
        if not _has_column(bind, _GRADE, "gpa_point"):
            op.add_column(_GRADE, sa.Column("gpa_point", sa.Numeric(4, 2), nullable=True))
        if not _has_column(bind, _GRADE, "gpa_policy_code"):
            op.add_column(_GRADE, sa.Column("gpa_policy_code", sa.String(80), nullable=True))
        if not _has_column(bind, _GRADE, "gpa_policy_version"):
            op.add_column(_GRADE, sa.Column("gpa_policy_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _GRADE):
        if _has_column(bind, _GRADE, "gpa_policy_version"):
            op.drop_column(_GRADE, "gpa_policy_version")
        if _has_column(bind, _GRADE, "gpa_policy_code"):
            op.drop_column(_GRADE, "gpa_policy_code")
        if _has_column(bind, _GRADE, "gpa_point"):
            op.drop_column(_GRADE, "gpa_point")
    if _has_table(bind, _POLICY):
        op.drop_table(_POLICY)
