"""Indexes for SQL-paginated student directory and batched contacts.

Revision ID: 0102_student_directory
Revises: 0101_wx_multi_tenant
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0102_student_directory"
down_revision = "0101_wx_multi_tenant"
branch_labels = None
depends_on = None

INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_student_tenant_active_id", "t_student_profile", ("tenant_id", "is_deleted", "id")),
    ("ix_student_tenant_class_active_id", "t_student_profile",
     ("tenant_id", "class_id", "is_deleted", "id")),
    ("ix_student_tenant_college_active_id", "t_student_profile",
     ("tenant_id", "college_id", "is_deleted", "id")),
    ("ix_student_tenant_major_active_id", "t_student_profile",
     ("tenant_id", "major_id", "is_deleted", "id")),
    ("ix_contact_tenant_student_type_active", "t_student_contact",
     ("tenant_id", "student_id", "contact_type", "is_deleted")),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    for name, table, columns in INDEXES:
        if table not in tables:
            continue
        existing = {item["name"] for item in inspect(bind).get_indexes(table)}
        if name not in existing:
            op.create_index(name, table, list(columns), unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    for name, table, _columns in reversed(INDEXES):
        if table in tables and name in {item["name"] for item in inspect(bind).get_indexes(table)}:
            op.drop_index(name, table_name=table)
