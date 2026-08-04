"""Add lease metadata for asynchronous student-affairs archive package generation.

Revision ID: 20260804_affairs_archive_async
Revises: 20260804_affairs_r2_merge
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260804_affairs_archive_async"
down_revision = "20260804_affairs_r2_merge"
branch_labels = None
depends_on = None

_TABLE = "t_affairs_archive_package"
_COLUMNS = (
    ("generation_attempts", sa.Column(
        "generation_attempts", sa.Integer(), nullable=False, server_default="0"
    )),
    ("generation_error", sa.Column(
        "generation_error", sa.String(length=1000), nullable=True
    )),
    ("generation_lease_token", sa.Column(
        "generation_lease_token", sa.String(length=64), nullable=True
    )),
    ("generation_lease_until", sa.Column(
        "generation_lease_until", sa.DateTime(), nullable=True
    )),
)
_INDEXES = (
    ("ix_affairs_archive_package_generation_lease_token", ["generation_lease_token"]),
    ("ix_affairs_archive_package_generation_lease_until", ["generation_lease_until"]),
)


def _schema_state() -> tuple[set[str], set[str]]:
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        raise RuntimeError(f"{_TABLE} must exist before applying {revision}")
    columns = {str(item["name"]) for item in inspector.get_columns(_TABLE)}
    indexes = {str(item["name"]) for item in inspector.get_indexes(_TABLE)}
    return columns, indexes


def upgrade() -> None:
    """Support both historical upgrades and fresh DBs created by metadata-based 0001."""
    columns, indexes = _schema_state()
    for name, column in _COLUMNS:
        if name not in columns:
            op.add_column(_TABLE, column)
            columns.add(name)
    for name, fields in _INDEXES:
        if name not in indexes:
            op.create_index(name, _TABLE, fields, unique=False)
            indexes.add(name)


def downgrade() -> None:
    columns, indexes = _schema_state()
    for name, _fields in reversed(_INDEXES):
        if name in indexes:
            op.drop_index(name, table_name=_TABLE)
            indexes.remove(name)
    for name, _column in reversed(_COLUMNS):
        if name in columns:
            op.drop_column(_TABLE, name)
            columns.remove(name)
