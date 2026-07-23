"""消息中心投递作业 / 运维字段

Revision ID: 0120_message_delivery_ops
Revises: 0119_message_center
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0120_message_delivery_ops"
down_revision = "0119_message_center"
branch_labels = None
depends_on = None


def _tables(bind) -> set[str]:
    return set(inspect(bind).get_table_names())


def _cols(bind, table: str) -> set[str]:
    if table not in _tables(bind):
        return set()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    if table not in _tables(bind):
        return set()
    return {i["name"] for i in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    camp = "t_message_campaign"
    if camp in _tables(bind):
        cols = _cols(bind, camp)
        if "ack_deadline_at" not in cols:
            op.add_column(camp, sa.Column("ack_deadline_at", sa.DateTime(), nullable=True))
        if "delivery_mode" not in cols:
            op.add_column(camp, sa.Column(
                "delivery_mode", sa.String(20), nullable=False,
                server_default="ASYNC", comment="SYNC/ASYNC"))

    job = "t_message_delivery_job"
    if job not in _tables(bind):
        op.create_table(
            job,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("campaign_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("cursor_start", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("batch_size", sa.Integer(), nullable=False, server_default="200"),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING",
                      comment="PENDING/PROCESSING/SUCCEEDED/RETRY_WAIT/DEAD"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("locked_by", sa.String(80), nullable=True),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_code", sa.String(80), nullable=True),
            sa.Column("recipient_slice_json", sa.JSON(), nullable=True),
            sa.Column("written_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("remark", sa.String(500), nullable=True),
        )
        idxs = _indexes(bind, job)
        if "ix_msg_delivery_job_status_retry" not in idxs:
            op.create_index(
                "ix_msg_delivery_job_status_retry", job,
                ["status", "next_retry_at", "id"])


def downgrade() -> None:
    bind = op.get_bind()
    if "t_message_delivery_job" in _tables(bind):
        op.drop_table("t_message_delivery_job")
