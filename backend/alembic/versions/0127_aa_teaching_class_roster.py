"""V2-02 独立教学班及名单版本。

仅新增兼容表，不删除或改写 AaTeachingTask 历史字段；存量数据由应用层显式投影和对账，
迁移本身不自动猜测、合并或删除生产业务记录。

Revision ID: 0127_aa_teaching_class_roster
Revises: 0126_aa_grade_task_uniqueness_guard
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0127_aa_teaching_class_roster"
down_revision = "0126_aa_grade_task_uniqueness_guard"
branch_labels = None
depends_on = None


def _tables(bind):
    return set(inspect(bind).get_table_names())


def _indexes(bind, table):
    if table not in _tables(bind):
        return set()
    return {row["name"] for row in inspect(bind).get_indexes(table)}


def _uniques(bind, table):
    if table not in _tables(bind):
        return set()
    return {row["name"] for row in inspect(bind).get_unique_constraints(table)}


def _ensure_index(bind, table, name, columns):
    if table in _tables(bind) and name not in _indexes(bind, table):
        op.create_index(name, table, columns)


def _ensure_unique(bind, table, name, columns):
    if table in _tables(bind) and name not in _uniques(bind, table) and name not in _indexes(bind, table):
        op.create_unique_constraint(name, table, columns)


def _common_columns():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)

    if "t_aa_teaching_class" not in tables:
        op.create_table(
            "t_aa_teaching_class",
            *_common_columns(),
            sa.Column("teaching_task_id", sa.BigInteger(), nullable=False, comment="兼容来源教学任务ID"),
            sa.Column("term_id", sa.BigInteger(), nullable=False),
            sa.Column("course_id", sa.BigInteger(), nullable=False),
            sa.Column("class_code", sa.String(length=80), nullable=False),
            sa.Column("class_name", sa.String(length=160), nullable=False),
            sa.Column("class_type", sa.String(length=24), nullable=False, server_default="ADMIN"),
            sa.Column("source_type", sa.String(length=32), nullable=False, server_default="TEACHING_TASK"),
            sa.Column("source_id", sa.BigInteger(), nullable=True),
            sa.Column("capacity", sa.Integer(), nullable=True),
            sa.Column("current_roster_version_id", sa.BigInteger(), nullable=True),
            sa.Column("current_roster_version_no", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("roster_status", sa.String(length=24), nullable=False, server_default="DRAFT"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="ACTIVE"),
            sa.Column("source_snapshot_json", sa.Text(), nullable=True),
            sa.UniqueConstraint("tenant_id", "teaching_task_id", name="uk_aa_tc_task"),
            sa.UniqueConstraint("tenant_id", "term_id", "class_code", name="uk_aa_tc_term_code"),
        )

    if "t_aa_teaching_class_teacher" not in tables:
        op.create_table(
            "t_aa_teaching_class_teacher",
            *_common_columns(),
            sa.Column("teaching_class_id", sa.BigInteger(), nullable=False),
            sa.Column("teacher_id", sa.BigInteger(), nullable=True),
            sa.Column("teacher_key", sa.String(length=100), nullable=False),
            sa.Column("teacher_name", sa.String(length=100), nullable=True),
            sa.Column("role_type", sa.String(length=24), nullable=False, server_default="PRIMARY"),
            sa.Column("start_week", sa.Integer(), nullable=True),
            sa.Column("end_week", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="ACTIVE"),
            sa.UniqueConstraint("tenant_id", "teaching_class_id", "teacher_key", "role_type", name="uk_aa_tc_teacher"),
        )

    if "t_aa_teaching_class_roster_version" not in tables:
        op.create_table(
            "t_aa_teaching_class_roster_version",
            *_common_columns(),
            sa.Column("teaching_class_id", sa.BigInteger(), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("source_type", sa.String(length=32), nullable=False),
            sa.Column("source_id", sa.BigInteger(), nullable=True),
            sa.Column("member_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("roster_hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="LOCKED"),
            sa.Column("reason", sa.String(length=500), nullable=True),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("locked_by", sa.String(length=100), nullable=True),
            sa.UniqueConstraint("tenant_id", "teaching_class_id", "version_no", name="uk_aa_tc_roster_version"),
        )

    if "t_aa_teaching_class_member" not in tables:
        op.create_table(
            "t_aa_teaching_class_member",
            *_common_columns(),
            sa.Column("teaching_class_id", sa.BigInteger(), nullable=False),
            sa.Column("roster_version_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("source_type", sa.String(length=32), nullable=False),
            sa.Column("source_id", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="ACTIVE"),
            sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("removed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "roster_version_id", "student_id", name="uk_aa_tc_member_version_student"),
        )

    _ensure_unique(bind, "t_aa_teaching_class", "uk_aa_tc_task", ["tenant_id", "teaching_task_id"])
    _ensure_unique(bind, "t_aa_teaching_class", "uk_aa_tc_term_code", ["tenant_id", "term_id", "class_code"])
    _ensure_unique(bind, "t_aa_teaching_class_teacher", "uk_aa_tc_teacher", ["tenant_id", "teaching_class_id", "teacher_key", "role_type"])
    _ensure_unique(bind, "t_aa_teaching_class_roster_version", "uk_aa_tc_roster_version", ["tenant_id", "teaching_class_id", "version_no"])
    _ensure_unique(bind, "t_aa_teaching_class_member", "uk_aa_tc_member_version_student", ["tenant_id", "roster_version_id", "student_id"])

    for table, name, columns in (
        ("t_aa_teaching_class", "ix_t_aa_teaching_class_tenant_id", ["tenant_id"]),
        ("t_aa_teaching_class", "ix_aa_tc_term_id", ["term_id"]),
        ("t_aa_teaching_class", "ix_aa_tc_course_id", ["course_id"]),
        ("t_aa_teaching_class", "ix_aa_tc_current_roster", ["current_roster_version_id"]),
        ("t_aa_teaching_class", "ix_aa_tc_term_course", ["tenant_id", "term_id", "course_id"]),
        ("t_aa_teaching_class", "ix_aa_tc_status", ["tenant_id", "status"]),
        ("t_aa_teaching_class_teacher", "ix_t_aa_teaching_class_teacher_tenant_id", ["tenant_id"]),
        ("t_aa_teaching_class_teacher", "ix_aa_tc_teacher_class", ["teaching_class_id"]),
        ("t_aa_teaching_class_teacher", "ix_aa_tc_teacher_key", ["tenant_id", "teacher_key", "status"]),
        ("t_aa_teaching_class_roster_version", "ix_t_aa_teaching_class_roster_version_tenant_id", ["tenant_id"]),
        ("t_aa_teaching_class_roster_version", "ix_aa_tc_roster_class", ["teaching_class_id"]),
        ("t_aa_teaching_class_roster_version", "ix_aa_tc_roster_status", ["tenant_id", "teaching_class_id", "status"]),
        ("t_aa_teaching_class_roster_version", "ix_aa_tc_roster_hash", ["tenant_id", "teaching_class_id", "roster_hash"]),
        ("t_aa_teaching_class_member", "ix_t_aa_teaching_class_member_tenant_id", ["tenant_id"]),
        ("t_aa_teaching_class_member", "ix_aa_tc_member_teaching_class", ["teaching_class_id"]),
        ("t_aa_teaching_class_member", "ix_aa_tc_member_roster_version", ["roster_version_id"]),
        ("t_aa_teaching_class_member", "ix_aa_tc_member_student_id", ["student_id"]),
        ("t_aa_teaching_class_member", "ix_aa_tc_member_student", ["tenant_id", "student_id", "status"]),
        ("t_aa_teaching_class_member", "ix_aa_tc_member_class", ["tenant_id", "teaching_class_id", "roster_version_id"]),
    ):
        _ensure_index(bind, table, name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)
    for table in (
        "t_aa_teaching_class_member",
        "t_aa_teaching_class_roster_version",
        "t_aa_teaching_class_teacher",
        "t_aa_teaching_class",
    ):
        if table in tables:
            op.drop_table(table)
