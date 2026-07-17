"""Tenant hot-path composite indexes for the ten-school production baseline.

Revision ID: 0100_tenant_hotpaths
Revises: a1198e75cb72
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0100_tenant_hotpaths"
down_revision = "a1198e75cb72"
branch_labels = None
depends_on = None


INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_msg_tenant_receiver_active_id", "t_unified_message",
     ("tenant_id", "receiver_id", "is_deleted", "id")),
    ("ix_msg_tenant_receiver_unread", "t_unified_message",
     ("tenant_id", "receiver_id", "is_deleted", "status")),
    ("ix_todo_tenant_student_status_id", "t_unified_todo",
     ("tenant_id", "student_id", "is_deleted", "status", "id")),
    ("ix_todo_tenant_assignee_status_id", "t_unified_todo",
     ("tenant_id", "assignee_id", "is_deleted", "status", "id")),
    ("ix_warning_tenant_student_status", "t_acad_warning",
     ("tenant_id", "acad_student_id", "is_deleted", "status")),
    ("ix_audit_tenant_created_id", "t_security_audit_log",
     ("tenant_id", "created_at", "id")),
    ("ix_audit_tenant_operator_created", "t_security_audit_log",
     ("tenant_id", "operator_id", "created_at")),
    ("ix_ori_student_tenant_profile_active", "t_orientation_student",
     ("tenant_id", "student_id", "is_deleted")),
    ("ix_acad_student_tenant_profile_active", "t_acad_student",
     ("tenant_id", "student_id", "is_deleted")),
    ("ix_emp_student_tenant_profile_active", "t_emp_student",
     ("tenant_id", "student_id", "is_deleted")),
    ("ix_intern_tenant_student_active", "t_internship_record",
     ("tenant_id", "student_id", "is_deleted")),
)


def _table_names(bind) -> set[str]:
    return set(inspect(bind).get_table_names())


def _index_names(bind, table: str) -> set[str]:
    return {item["name"] for item in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    for name, table, columns in INDEXES:
        if table in tables and name not in _index_names(bind, table):
            op.create_index(name, table, list(columns), unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    for name, table, _columns in reversed(INDEXES):
        if table in tables and name in _index_names(bind, table):
            op.drop_index(name, table_name=table)
