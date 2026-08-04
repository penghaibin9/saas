"""PLAT-12：备份恢复验证与灾备（证据元数据）。

Revision ID: 0173_disaster_recovery
Revises: a98ccd2d4474
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0173_disaster_recovery"
down_revision = "a98ccd2d4474"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0173_disaster_recovery requires MySQL")


def _common() -> list:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())

    if not insp.has_table("t_backup_evidence"):
        op.create_table(
            "t_backup_evidence",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("backup_type", sa.String(30), nullable=False),
            sa.Column("method", sa.String(30), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("location_ref", sa.String(500)),
            sa.Column("size_bytes", sa.BigInteger()),
            sa.Column("checksum_sha256", sa.String(64)),
            sa.Column("table_count", sa.BigInteger()),
            sa.Column("detail_json", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.String(1000)),
            sa.Column("captured_by", sa.BigInteger()),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_backup_evidence_type", "t_backup_evidence", ["backup_type"])
        op.create_index("ix_t_backup_evidence_status", "t_backup_evidence", ["status"])

    if not insp.has_table("t_restore_drill"):
        op.create_table(
            "t_restore_drill",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("backup_evidence_id", sa.BigInteger()),
            sa.Column("drill_type", sa.String(30), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("target_description", sa.String(300)),
            sa.Column("detail_json", sa.JSON(), nullable=False),
            sa.Column("performed_by", sa.BigInteger()),
            sa.Column("performed_at", sa.DateTime(), nullable=False),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_restore_drill_evidence", "t_restore_drill", ["backup_evidence_id"])
        op.create_index("ix_t_restore_drill_status", "t_restore_drill", ["status"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_restore_drill", "t_backup_evidence"):
        if insp.has_table(table):
            op.drop_table(table)
