"""Normalize role-assignment scope collation after the stable-scope migration.

Revision ID: 20260830_role_scope_collation
Revises: 20260829_pr236_main_merge

``t_role`` is an older table normalized to ``utf8mb4_unicode_ci`` by the
repository-wide schema reconcile. ``t_role_assignment_scope`` was introduced
later without an explicit table collation, so a clean MySQL 8 database created
it with ``utf8mb4_0900_ai_ci``. Cross-table role-code joins then fail with
MySQL error 1267 instead of reporting relationship violations.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "20260830_role_scope_collation"
down_revision = "20260829_pr236_main_merge"
branch_labels = None
depends_on = None

TARGET_CHARSET = "utf8mb4"
TARGET_COLLATION = "utf8mb4_unicode_ci"

assert len(revision) <= 32


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql" or not sa.inspect(bind).has_table(
        "t_role_assignment_scope"
    ):
        return
    schema = bind.execute(text("SELECT DATABASE()")).scalar_one()
    current = bind.execute(
        text("""
            SELECT TABLE_COLLATION
              FROM information_schema.TABLES
             WHERE TABLE_SCHEMA=:schema
               AND TABLE_NAME='t_role_assignment_scope'
        """),
        {"schema": schema},
    ).scalar_one_or_none()
    if current != TARGET_COLLATION:
        bind.execute(text(
            "ALTER TABLE `t_role_assignment_scope` "
            f"CONVERT TO CHARACTER SET {TARGET_CHARSET} COLLATE {TARGET_COLLATION}"
        ))


def downgrade() -> None:
    # Collation normalization is a compatibility repair. Restoring the server's
    # former default would reintroduce nondeterministic schemas and error 1267.
    pass
