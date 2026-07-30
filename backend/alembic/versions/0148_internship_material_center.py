"""公共文件冻结中心阶段 4：岗位实习材料、版本与真实归档清单

Revision ID: 0148_internship_material_center
Revises: 0147_data_exchange_jobs
Create Date: 2026-07-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0148_internship_material_center"
down_revision = "0147_data_exchange_jobs"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {item["name"] for item in _inspector().get_columns(table)}


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {item["name"] for item in _inspector().get_indexes(table)}


def _uniques(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {item.get("name") for item in _inspector().get_unique_constraints(table) if item.get("name")}


def upgrade() -> None:
    tables = _tables()

    if "t_file_asset" not in tables:
        op.create_table(
            "t_file_asset",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("asset_code", sa.String(180), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("category_code", sa.String(80), nullable=False),
            sa.Column("owner_type", sa.String(30), nullable=False, server_default="BUSINESS_OBJECT"),
            sa.Column("owner_id", sa.String(64)),
            sa.Column("current_version_id", sa.BigInteger()),
            sa.Column("lifecycle_status", sa.String(30), nullable=False, server_default="ACTIVE"),
            sa.Column("version_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sensitivity_level", sa.String(30), nullable=False, server_default="PERSONAL"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "asset_code", name="uk_file_asset_code"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_t_file_asset_tenant_id", "t_file_asset", ["tenant_id"])
        op.create_index("ix_t_file_asset_category_code", "t_file_asset", ["category_code"])
        op.create_index("ix_t_file_asset_owner_id", "t_file_asset", ["owner_id"])
        op.create_index("ix_t_file_asset_current_version_id", "t_file_asset", ["current_version_id"])
        op.create_index("ix_file_asset_owner", "t_file_asset", ["tenant_id", "owner_type", "owner_id"])
        op.create_index("ix_file_asset_category", "t_file_asset", ["tenant_id", "category_code", "lifecycle_status"])

    tables = _tables()
    if "t_file_version" not in tables:
        op.create_table(
            "t_file_version",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("asset_id", sa.BigInteger(), nullable=False),
            sa.Column("file_object_id", sa.BigInteger(), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("source_channel", sa.String(40), nullable=False, server_default="LEGACY_ADAPTER"),
            sa.Column("uploader_user_id", sa.String(64)),
            sa.Column("uploader_name_snapshot", sa.String(100)),
            sa.Column("submit_comment", sa.String(500)),
            sa.Column("status", sa.String(30), nullable=False, server_default="UPLOADED"),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("submitted_at", sa.DateTime()),
            sa.Column("invalidated_at", sa.DateTime()),
            sa.Column("invalidated_by", sa.String(100)),
            sa.Column("invalid_reason", sa.String(500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "asset_id", "version_no", name="uk_file_version_no"),
            sa.UniqueConstraint("tenant_id", "asset_id", "file_object_id", name="uk_file_version_object"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_t_file_version_tenant_id", "t_file_version", ["tenant_id"])
        op.create_index("ix_t_file_version_asset_id", "t_file_version", ["asset_id"])
        op.create_index("ix_t_file_version_file_object_id", "t_file_version", ["file_object_id"])
        op.create_index("ix_t_file_version_is_current", "t_file_version", ["is_current"])
        op.create_index("ix_file_version_current", "t_file_version", ["tenant_id", "asset_id", "is_current", "status"])

    tables = _tables()
    if "t_archive_manifest" not in tables:
        op.create_table(
            "t_archive_manifest",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("module_code", sa.String(64), nullable=False),
            sa.Column("archive_type", sa.String(64), nullable=False),
            sa.Column("target_type", sa.String(40), nullable=False),
            sa.Column("target_id", sa.String(64), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(30), nullable=False, server_default="PREPARED"),
            sa.Column("rule_version", sa.String(64)),
            sa.Column("manifest_sha256", sa.String(64)),
            sa.Column("package_file_id", sa.BigInteger()),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("frozen_at", sa.DateTime()),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("revoked_by", sa.String(100)),
            sa.Column("revoke_reason", sa.String(500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "module_code", "archive_type", "target_type", "target_id", "revision", name="uk_archive_manifest_revision"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_t_archive_manifest_tenant_id", "t_archive_manifest", ["tenant_id"])
        op.create_index("ix_t_archive_manifest_module_code", "t_archive_manifest", ["module_code"])
        op.create_index("ix_t_archive_manifest_target_id", "t_archive_manifest", ["target_id"])
        op.create_index("ix_t_archive_manifest_manifest_sha256", "t_archive_manifest", ["manifest_sha256"])
        op.create_index("ix_t_archive_manifest_package_file_id", "t_archive_manifest", ["package_file_id"])
        op.create_index("ix_archive_manifest_target", "t_archive_manifest", ["tenant_id", "module_code", "target_type", "target_id", "status"])

    tables = _tables()
    if "t_archive_manifest_item" not in tables:
        op.create_table(
            "t_archive_manifest_item",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("manifest_id", sa.BigInteger(), nullable=False),
            sa.Column("material_code", sa.String(100), nullable=False),
            sa.Column("asset_id", sa.BigInteger(), nullable=False),
            sa.Column("version_id", sa.BigInteger(), nullable=False),
            sa.Column("file_object_id", sa.BigInteger(), nullable=False),
            sa.Column("file_name_snapshot", sa.String(300), nullable=False),
            sa.Column("size_snapshot", sa.BigInteger()),
            sa.Column("sha256_snapshot", sa.String(64)),
            sa.Column("review_status", sa.String(40)),
            sa.Column("scan_result", sa.String(30), nullable=False),
            sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "manifest_id", "version_id", "material_code", name="uk_archive_manifest_item_version"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_t_archive_manifest_item_tenant_id", "t_archive_manifest_item", ["tenant_id"])
        op.create_index("ix_t_archive_manifest_item_manifest_id", "t_archive_manifest_item", ["manifest_id"])
        op.create_index("ix_t_archive_manifest_item_asset_id", "t_archive_manifest_item", ["asset_id"])
        op.create_index("ix_t_archive_manifest_item_version_id", "t_archive_manifest_item", ["version_id"])
        op.create_index("ix_t_archive_manifest_item_file_object_id", "t_archive_manifest_item", ["file_object_id"])
        op.create_index("ix_archive_manifest_item_order", "t_archive_manifest_item", ["tenant_id", "manifest_id", "sort_no", "id"])

    if "t_file_binding" in _tables():
        cols = _columns("t_file_binding")
        additions = [
            ("asset_id", sa.Column("asset_id", sa.BigInteger())),
            ("version_id", sa.Column("version_id", sa.BigInteger())),
            ("module_code", sa.Column("module_code", sa.String(64))),
            ("student_id", sa.Column("student_id", sa.BigInteger())),
            ("college_id", sa.Column("college_id", sa.BigInteger())),
            ("class_id", sa.Column("class_id", sa.BigInteger())),
            ("data_scope_snapshot_json", sa.Column("data_scope_snapshot_json", sa.JSON())),
            ("invalidated_at", sa.Column("invalidated_at", sa.DateTime())),
        ]
        for name, column in additions:
            if name not in cols:
                op.add_column("t_file_binding", column)
        indexes = _indexes("t_file_binding")
        for name, columns in (
            ("ix_t_file_binding_asset_id", ["asset_id"]),
            ("ix_t_file_binding_version_id", ["version_id"]),
            ("ix_t_file_binding_module_code", ["module_code"]),
            ("ix_t_file_binding_student_id", ["student_id"]),
            ("ix_t_file_binding_college_id", ["college_id"]),
            ("ix_t_file_binding_class_id", ["class_id"]),
            ("ix_file_binding_asset_current", ["tenant_id", "asset_id", "version_id", "is_current"]),
        ):
            if name not in indexes:
                op.create_index(name, "t_file_binding", columns)
        if "uk_file_binding_version_relation" not in _uniques("t_file_binding"):
            op.create_unique_constraint("uk_file_binding_version_relation", "t_file_binding", ["tenant_id", "version_id", "module_code", "biz_type", "biz_id", "relation_type"])


def downgrade() -> None:
    if "t_file_binding" in _tables():
        if "uk_file_binding_version_relation" in _uniques("t_file_binding"):
            op.drop_constraint("uk_file_binding_version_relation", "t_file_binding", type_="unique")
        for index_name in (
            "ix_file_binding_asset_current", "ix_t_file_binding_class_id", "ix_t_file_binding_college_id",
            "ix_t_file_binding_student_id", "ix_t_file_binding_module_code",
            "ix_t_file_binding_version_id", "ix_t_file_binding_asset_id",
        ):
            if index_name in _indexes("t_file_binding"):
                op.drop_index(index_name, table_name="t_file_binding")
        for column_name in (
            "invalidated_at", "data_scope_snapshot_json", "class_id", "college_id",
            "student_id", "module_code", "version_id", "asset_id",
        ):
            if column_name in _columns("t_file_binding"):
                op.drop_column("t_file_binding", column_name)
    for table in ("t_archive_manifest_item", "t_archive_manifest", "t_file_version", "t_file_asset"):
        if table in _tables():
            op.drop_table(table)
