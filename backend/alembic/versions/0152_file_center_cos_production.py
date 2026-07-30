"""阶段 8：COS 正式对象身份、迁移与核验字段。

Revision ID: 0152_file_center_cos_production
Revises: 0151_graduation_manifest_evidence
Create Date: 2026-07-31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0152_file_center_cos_production"
down_revision = "0151_graduation_manifest_evidence"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("0152_file_center_cos_production requires MySQL")
    return {item["name"] for item in inspect(bind).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    columns = _columns("t_file_object")
    additions = (
        ("bucket_name", sa.Column("bucket_name", sa.String(150))),
        ("object_key", sa.Column("object_key", sa.String(500))),
        ("etag", sa.Column("etag", sa.String(128))),
        ("storage_migrated_at", sa.Column("storage_migrated_at", sa.DateTime())),
        ("storage_verified_at", sa.Column("storage_verified_at", sa.DateTime())),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("t_file_object", column)
    op.execute(text(
        "UPDATE t_file_object SET object_key=file_key "
        "WHERE object_key IS NULL OR object_key=''"
    ))
    indexes = _indexes("t_file_object")
    if "ix_file_storage_object" not in indexes:
        op.create_index(
            "ix_file_storage_object",
            "t_file_object",
            ["storage_backend", "bucket_name", "object_key"],
        )
    if "ix_file_storage_migration" not in indexes:
        op.create_index(
            "ix_file_storage_migration",
            "t_file_object",
            ["tenant_id", "storage_backend", "storage_migrated_at", "id"],
        )


def downgrade() -> None:
    indexes = _indexes("t_file_object")
    for name in ("ix_file_storage_migration", "ix_file_storage_object"):
        if name in indexes:
            op.drop_index(name, table_name="t_file_object")
    columns = _columns("t_file_object")
    for name in ("storage_verified_at", "storage_migrated_at", "etag", "object_key", "bucket_name"):
        if name in columns:
            op.drop_column("t_file_object", name)
