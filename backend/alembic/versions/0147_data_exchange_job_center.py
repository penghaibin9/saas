"""公共文件中心阶段 3：统一导入导出任务中心

Revision ID: 0147_data_exchange_jobs
Revises: 0146_file_access_clients
Create Date: 2026-07-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0147_data_exchange_jobs"
down_revision = "0146_file_access_clients"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    tables = _tables()
    if "t_import_job" not in tables:
        op.create_table(
            "t_import_job",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("module_code", sa.String(64), nullable=False),
            sa.Column("import_type", sa.String(80), nullable=False),
            sa.Column("source_file_id", sa.BigInteger()),
            sa.Column("adapter_type", sa.String(50), nullable=False),
            sa.Column("adapter_ref", sa.String(128), nullable=False),
            sa.Column("template_version", sa.String(32), nullable=False, server_default="v1"),
            sa.Column("status", sa.String(32), nullable=False, server_default="VALIDATED"),
            sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("confirmed_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("operator_id", sa.BigInteger()),
            sa.Column("operator_name", sa.String(100)),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("confirmed_at", sa.DateTime()),
            sa.Column("lease_token", sa.String(96)),
            sa.Column("lease_started_at", sa.DateTime()),
            sa.Column("error_receipt_file_id", sa.BigInteger()),
            sa.Column("credential_receipt_file_id", sa.BigInteger()),
            sa.Column("source_snapshot_json", sa.JSON()),
            sa.Column("result_json", sa.JSON()),
            sa.Column("error_message", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "adapter_type", "adapter_ref", name="uk_import_job_adapter_ref"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
        )
        op.create_index("ix_t_import_job_tenant_id", "t_import_job", ["tenant_id"])
        op.create_index("ix_t_import_job_module_code", "t_import_job", ["module_code"])
        op.create_index("ix_t_import_job_import_type", "t_import_job", ["import_type"])
        op.create_index("ix_t_import_job_source_file_id", "t_import_job", ["source_file_id"])
        op.create_index("ix_t_import_job_adapter_type", "t_import_job", ["adapter_type"])
        op.create_index("ix_t_import_job_status", "t_import_job", ["status"])
        op.create_index("ix_t_import_job_operator_id", "t_import_job", ["operator_id"])
        op.create_index("ix_t_import_job_expires_at", "t_import_job", ["expires_at"])
        op.create_index("ix_import_job_list", "t_import_job", ["tenant_id", "status", "created_at", "id"])
        op.create_index("ix_import_job_owner", "t_import_job", ["tenant_id", "operator_id", "created_at"])

    tables = _tables()
    if "t_import_row_error" not in tables:
        op.create_table(
            "t_import_row_error",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("import_job_id", sa.BigInteger(), nullable=False),
            sa.Column("sheet_name", sa.String(100)),
            sa.Column("row_no", sa.Integer()),
            sa.Column("field_code", sa.String(100)),
            sa.Column("error_code", sa.String(80)),
            sa.Column("error_message", sa.String(1000), nullable=False),
            sa.Column("raw_snapshot_json", sa.JSON()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
        )
        op.create_index("ix_t_import_row_error_tenant_id", "t_import_row_error", ["tenant_id"])
        op.create_index("ix_t_import_row_error_import_job_id", "t_import_row_error", ["import_job_id"])
        op.create_index("ix_import_row_error_job_row", "t_import_row_error", ["tenant_id", "import_job_id", "row_no"])

    tables = _tables()
    if "t_export_job" not in tables:
        op.create_table(
            "t_export_job",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("module_code", sa.String(64), nullable=False),
            sa.Column("export_type", sa.String(80), nullable=False),
            sa.Column("purpose", sa.String(500)),
            sa.Column("adapter_type", sa.String(50)),
            sa.Column("adapter_ref", sa.String(128)),
            sa.Column("filter_snapshot_json", sa.JSON()),
            sa.Column("data_scope_snapshot_json", sa.JSON()),
            sa.Column("status", sa.String(32), nullable=False, server_default="CREATED"),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("file_object_id", sa.BigInteger()),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("downloaded_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("revoke_reason", sa.String(500)),
            sa.Column("operator_id", sa.BigInteger()),
            sa.Column("finished_at", sa.DateTime()),
            sa.Column("result_json", sa.JSON()),
            sa.Column("error_message", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint(
                "tenant_id", "adapter_type", "adapter_ref", "export_type",
                name="uk_export_job_adapter_ref",
            ),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
        )
        op.create_index("ix_t_export_job_tenant_id", "t_export_job", ["tenant_id"])
        op.create_index("ix_t_export_job_module_code", "t_export_job", ["module_code"])
        op.create_index("ix_t_export_job_export_type", "t_export_job", ["export_type"])
        op.create_index("ix_t_export_job_adapter_type", "t_export_job", ["adapter_type"])
        op.create_index("ix_t_export_job_status", "t_export_job", ["status"])
        op.create_index("ix_t_export_job_file_object_id", "t_export_job", ["file_object_id"])
        op.create_index("ix_t_export_job_expires_at", "t_export_job", ["expires_at"])
        op.create_index("ix_t_export_job_operator_id", "t_export_job", ["operator_id"])
        op.create_index("ix_export_job_list", "t_export_job", ["tenant_id", "status", "created_at", "id"])
        op.create_index("ix_export_job_owner", "t_export_job", ["tenant_id", "operator_id", "created_at"])


def downgrade() -> None:
    tables = _tables()
    for table in ("t_export_job", "t_import_row_error", "t_import_job"):
        if table in tables:
            op.drop_table(table)
