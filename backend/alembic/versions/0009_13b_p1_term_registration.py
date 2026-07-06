"""13B-P1: 建教务时间轴 3 表 + 学籍 3 表（term/calendar/time_slot + status_change/registration_batch/registration）

Revision ID: 0009_13b_p1_term_registration
Revises: 0008_13a_p6_dorm_archive
Create Date: 2026-07-06

学籍状态受控扩展 t_student_profile.student_status 枚举（零加列，仅扩取值），写侧唯一经 change_student_status()。
唯一键：t_aa_term(tenant,year_code,term_no)、t_aa_registration(tenant,batch,student)。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0009_13b_p1_term_registration"
down_revision = "0008_13a_p6_dorm_archive"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
TERM = "t_aa_term"
CAL = "t_aa_calendar_event"
SLOT = "t_aa_time_slot"
SC = "t_aa_status_change"
RB = "t_aa_registration_batch"
REG = "t_aa_registration"


def _has(bind, table):
    return table in inspect(bind).get_table_names()


def _pk_tenant(*extra):
    return [
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        *extra,
    ]


def _common_cols():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def _create(bind, table, cols, indexes=(), uniques=()):
    if _has(bind, table):
        return
    op.create_table(table, *cols)
    for ix_col in indexes:
        op.create_index(f"ix_{table}_{ix_col}", table, [ix_col])
    for name, ucols in uniques:
        op.create_unique_constraint(name, table, list(ucols))


def upgrade() -> None:
    bind = op.get_bind()

    _create(bind, TERM, _pk_tenant(
        sa.Column("year_code", sa.String(length=20), nullable=False),
        sa.Column("term_no", sa.Integer(), nullable=False),
        sa.Column("term_name", sa.String(length=100), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("teaching_weeks", sa.Integer(), nullable=True),
        sa.Column("exam_week_start", sa.Integer(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "year_code", "status"),
       uniques=(("uk_aa_term", ("tenant_id", "year_code", "term_no")),))

    _create(bind, CAL, _pk_tenant(
        sa.Column("term_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("swap_to_date", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.String(length=500), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "term_id"))

    _create(bind, SLOT, _pk_tenant(
        sa.Column("slot_no", sa.Integer(), nullable=False),
        sa.Column("slot_name", sa.String(length=50), nullable=True),
        sa.Column("start_time", sa.String(length=10), nullable=True),
        sa.Column("end_time", sa.String(length=10), nullable=True),
        sa.Column("campus_code", sa.String(length=50), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id",))

    _create(bind, SC, _pk_tenant(
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("change_type", sa.String(length=50), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=True),
        sa.Column("from_college_id", sa.BigInteger(), nullable=True),
        sa.Column("from_major_id", sa.BigInteger(), nullable=True),
        sa.Column("from_class_id", sa.BigInteger(), nullable=True),
        sa.Column("to_college_id", sa.BigInteger(), nullable=True),
        sa.Column("to_major_id", sa.BigInteger(), nullable=True),
        sa.Column("to_class_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("effective_date", sa.DateTime(), nullable=True),
        sa.Column("term_code", sa.String(length=50), nullable=True),
        sa.Column("source_biz_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "student_id", "change_type", "status", "workflow_instance_id"))

    _create(bind, RB, _pk_tenant(
        sa.Column("batch_name", sa.String(length=200), nullable=False),
        sa.Column("register_type", sa.String(length=20), nullable=False),
        sa.Column("term_id", sa.BigInteger(), nullable=True),
        sa.Column("window_start", sa.DateTime(), nullable=True),
        sa.Column("window_end", sa.DateTime(), nullable=True),
        sa.Column("scope_json", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "term_id", "status"))

    _create(bind, REG, _pk_tenant(
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("precheck_json", sa.String(length=2000), nullable=True),
        sa.Column("register_at", sa.DateTime(), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "batch_id", "student_id", "status"),
       uniques=(("uk_aa_registration", ("tenant_id", "batch_id", "student_id")),))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (REG, RB, SC, SLOT, CAL, TERM):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
