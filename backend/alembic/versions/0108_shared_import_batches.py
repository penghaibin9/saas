"""Generic multi-instance Dry-Run batches.

Revision ID: 0108_shared_import_batches
Revises: 0107_shared_identity_batch

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时本表可能已提前
创建，故先查表再执行原始 DDL（同 0103/0104/0105 约定）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0108_shared_import_batches"
down_revision = "0107_shared_identity_batch"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("t_shared_import_batch"):
        op.create_table(
            "t_shared_import_batch",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("namespace", sa.String(80), nullable=False),
            sa.Column("batch_no", sa.String(100), nullable=False),
            sa.Column("operator_key", sa.String(160)),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("errors_json", sa.JSON(), nullable=False),
            sa.Column("public_result_json", sa.JSON()),
            sa.Column("request_id", sa.String(160)),
            sa.Column("claim_token", sa.String(64)),
            sa.Column("claim_started_at", sa.DateTime()),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("confirmed_at", sa.DateTime()),
            sa.Column("last_error", sa.Text()),
            sa.UniqueConstraint("tenant_id", "namespace", "batch_no", name="uk_shared_import_batch_no"),
            sa.UniqueConstraint("tenant_id", "namespace", "request_id", name="uk_shared_import_request_id"),
        )
        for column in ("tenant_id", "namespace", "batch_no", "operator_key", "status", "claim_token", "expires_at"):
            op.create_index(f"ix_t_shared_import_batch_{column}", "t_shared_import_batch", [column])


def downgrade() -> None:
    if _has_table("t_shared_import_batch"):
        op.drop_table("t_shared_import_batch")
