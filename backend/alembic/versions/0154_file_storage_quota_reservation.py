"""阶段 9：并发安全的文件存储配额预留账本。

Revision ID: 0154_file_storage_quota_reservation
Revises: 0153_file_storage_governance
Create Date: 2026-07-31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0154_file_storage_quota_reservation"
down_revision = "0153_file_storage_governance"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0154_file_storage_quota_reservation requires MySQL")


def upgrade() -> None:
    _require_mysql()
    if inspect(op.get_bind()).has_table("t_file_storage_quota_reservation"):
        return
    op.create_table(
        "t_file_storage_quota_reservation",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("reservation_key", sa.String(160), nullable=False),
        sa.Column("module_code", sa.String(64), nullable=False, server_default="SHARED"),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(500), nullable=False),
        sa.Column("reserved_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="HELD"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_file_id", sa.BigInteger()),
        sa.Column("consumed_at", sa.DateTime()),
        sa.Column("released_at", sa.DateTime()),
        sa.Column("release_reason", sa.String(300)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "reservation_key", name="uk_file_quota_reservation_key"),
    )
    op.create_index(
        "ix_file_quota_reservation_active",
        "t_file_storage_quota_reservation",
        ["tenant_id", "status", "expires_at", "id"],
    )
    op.create_index(
        "ix_file_quota_reservation_source",
        "t_file_storage_quota_reservation",
        ["tenant_id", "source_type", "source_id"],
    )


def downgrade() -> None:
    _require_mysql()
    if inspect(op.get_bind()).has_table("t_file_storage_quota_reservation"):
        op.drop_table("t_file_storage_quota_reservation")
