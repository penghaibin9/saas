"""Add auditable return-from-leave fields.

Revision ID: 0047_internship_leave_return
Revises: 0046_internship_application
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0047_internship_leave_return"
down_revision = "0046_internship_application"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    return ({x["name"] for x in inspector.get_columns(table)}
            if table in inspector.get_table_names() else set())


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "t_internship_leave")
    for name, column in (
        ("returned_at", sa.Column("returned_at", sa.DateTime(), nullable=True)),
        ("return_note", sa.Column("return_note", sa.String(500), nullable=True)),
        ("return_file_id", sa.Column("return_file_id", sa.String(64), nullable=True)),
    ):
        if columns and name not in columns:
            op.add_column("t_internship_leave", column)


def downgrade() -> None:
    bind = op.get_bind()
    for name in ("return_file_id", "return_note", "returned_at"):
        if name in _columns(bind, "t_internship_leave"):
            op.drop_column("t_internship_leave", name)
