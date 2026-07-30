"""阶段 6：归档 Manifest 冻结上传人和提交时间证据。

Revision ID: 0151_graduation_manifest_evidence
Revises: 0150_graduation_material_center
Create Date: 2026-07-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0151_graduation_manifest_evidence"
down_revision = "0150_graduation_material_center"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("0151_graduation_manifest_evidence requires MySQL")
    return {item["name"] for item in inspect(bind).get_columns("t_archive_manifest_item")}


def upgrade() -> None:
    columns = _columns()
    if "uploader_snapshot" not in columns:
        op.add_column("t_archive_manifest_item", sa.Column("uploader_snapshot", sa.String(100)))
    if "submitted_at_snapshot" not in columns:
        op.add_column("t_archive_manifest_item", sa.Column("submitted_at_snapshot", sa.DateTime()))


def downgrade() -> None:
    columns = _columns()
    if "submitted_at_snapshot" in columns:
        op.drop_column("t_archive_manifest_item", "submitted_at_snapshot")
    if "uploader_snapshot" in columns:
        op.drop_column("t_archive_manifest_item", "uploader_snapshot")
