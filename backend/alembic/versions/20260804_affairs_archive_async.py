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


def upgrade() -> None:
    op.add_column("t_affairs_archive_package", sa.Column(
        "generation_attempts", sa.Integer(), nullable=False, server_default="0"
    ))
    op.add_column("t_affairs_archive_package", sa.Column(
        "generation_error", sa.String(length=1000), nullable=True
    ))
    op.add_column("t_affairs_archive_package", sa.Column(
        "generation_lease_token", sa.String(length=64), nullable=True
    ))
    op.add_column("t_affairs_archive_package", sa.Column(
        "generation_lease_until", sa.DateTime(), nullable=True
    ))
    op.create_index(
        "ix_affairs_archive_package_generation_lease_token",
        "t_affairs_archive_package", ["generation_lease_token"], unique=False,
    )
    op.create_index(
        "ix_affairs_archive_package_generation_lease_until",
        "t_affairs_archive_package", ["generation_lease_until"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_affairs_archive_package_generation_lease_until", table_name="t_affairs_archive_package")
    op.drop_index("ix_affairs_archive_package_generation_lease_token", table_name="t_affairs_archive_package")
    op.drop_column("t_affairs_archive_package", "generation_lease_until")
    op.drop_column("t_affairs_archive_package", "generation_lease_token")
    op.drop_column("t_affairs_archive_package", "generation_error")
    op.drop_column("t_affairs_archive_package", "generation_attempts")
