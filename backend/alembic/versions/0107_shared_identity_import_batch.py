"""Persistent multi-instance identity import batches.

Revision ID: 0107_shared_identity_batch
Revises: 0106_runtime_presets

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时本表可能已提前
创建，故先查表再执行原始 DDL（同 0103/0104/0105 约定）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0107_shared_identity_batch"
down_revision = "0106_runtime_presets"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("t_identity_import_batch"):
        op.create_table(
            "t_identity_import_batch",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("batch_no", sa.String(64), nullable=False),
            sa.Column("operator_key", sa.String(160), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_sha256", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("raw_rows_json", sa.JSON(), nullable=False),
            sa.Column("errors_json", sa.JSON(), nullable=False),
            sa.Column("pre_errors_json", sa.JSON(), nullable=False),
            sa.Column("report_json", sa.JSON(), nullable=False),
            sa.Column("relationships_json", sa.JSON(), nullable=False),
            sa.Column("relation_errors_json", sa.JSON(), nullable=False),
            sa.Column("public_result_json", sa.JSON()),
            sa.Column("claim_token", sa.String(64)),
            sa.Column("claim_started_at", sa.DateTime()),
            sa.Column("confirmed_at", sa.DateTime()),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("last_error", sa.Text()),
            sa.UniqueConstraint("tenant_id", "batch_no", name="uk_identity_import_batch_no"),
        )
        for column in ("tenant_id", "batch_no", "operator_key", "status", "claim_token", "expires_at"):
            op.create_index(f"ix_t_identity_import_batch_{column}", "t_identity_import_batch", [column])


def downgrade() -> None:
    if _has_table("t_identity_import_batch"):
        op.drop_table("t_identity_import_batch")
