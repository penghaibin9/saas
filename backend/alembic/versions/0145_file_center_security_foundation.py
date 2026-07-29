"""公共文件中心 P0 安全底座

Revision ID: 0145_file_security_foundation
Revises: aa_final_20260729
Create Date: 2026-07-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0145_file_security_foundation"
down_revision = "aa_final_20260729"
branch_labels = None
depends_on = None

FILE = "t_file_object"
SCAN = "t_file_scan_record"
SESSION = "t_file_upload_session"
JOB = "t_file_job"


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    existing = _columns(FILE)
    additions = [
        ("storage_backend", sa.Column("storage_backend", sa.String(30), nullable=False, server_default="local")),
        ("storage_zone", sa.Column("storage_zone", sa.String(30), nullable=False, server_default="ACTIVE")),
        ("upload_source", sa.Column("upload_source", sa.String(30), nullable=False, server_default="USER")),
        ("scan_required", sa.Column("scan_required", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("scan_status", sa.Column("scan_status", sa.String(30), nullable=False, server_default="NOT_REQUIRED")),
        ("scan_attempts", sa.Column("scan_attempts", sa.Integer(), nullable=False, server_default="0")),
        ("scan_engine", sa.Column("scan_engine", sa.String(50))),
        ("scan_engine_version", sa.Column("scan_engine_version", sa.String(120))),
        ("scan_signature_version", sa.Column("scan_signature_version", sa.String(120))),
        ("scan_last_error", sa.Column("scan_last_error", sa.Text())),
        ("scanned_at", sa.Column("scanned_at", sa.DateTime())),
        ("available_at", sa.Column("available_at", sa.DateTime())),
        ("rejected_at", sa.Column("rejected_at", sa.DateTime())),
    ]
    if FILE in _tables():
        with op.batch_alter_table(FILE) as batch:
            for name, column in additions:
                if name not in existing:
                    batch.add_column(column)
        indexes = _indexes(FILE)
        if "ix_t_file_object_scan_required" not in indexes:
            op.create_index("ix_t_file_object_scan_required", FILE, ["scan_required"])
        if "ix_t_file_object_scan_status" not in indexes:
            op.create_index("ix_t_file_object_scan_status", FILE, ["scan_status"])
        if "ix_file_object_scan_queue" not in indexes:
            op.create_index("ix_file_object_scan_queue", FILE, ["tenant_id", "scan_required", "scan_status", "created_at"])

    tables = _tables()
    if SCAN not in tables:
        op.create_table(
            SCAN, *_common_columns(),
            sa.Column("file_id", sa.BigInteger(), nullable=False),
            sa.Column("attempt", sa.Integer(), nullable=False),
            sa.Column("engine", sa.String(50), nullable=False, server_default="CLAMAV"),
            sa.Column("engine_version", sa.String(120)),
            sa.Column("signature_version", sa.String(120)),
            sa.Column("result", sa.String(30), nullable=False),
            sa.Column("threat_name", sa.String(300)),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("error_code", sa.String(80)),
            sa.Column("error_message", sa.Text()),
            sa.Column("details_json", sa.JSON()),
            sa.UniqueConstraint("tenant_id", "file_id", "attempt", name="uk_file_scan_record_attempt"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    scan_indexes = _indexes(SCAN)
    for name, cols in (
        ("ix_t_file_scan_record_tenant_id", ["tenant_id"]),
        ("ix_t_file_scan_record_file_id", ["file_id"]),
        ("ix_file_scan_record_result", ["tenant_id", "result", "created_at"]),
    ):
        if name not in scan_indexes:
            op.create_index(name, SCAN, cols)

    tables = _tables()
    if SESSION not in tables:
        op.create_table(
            SESSION, *_common_columns(),
            sa.Column("session_key", sa.String(64), nullable=False),
            sa.Column("file_id", sa.BigInteger()),
            sa.Column("status", sa.String(30), nullable=False, server_default="CREATED"),
            sa.Column("source", sa.String(30), nullable=False, server_default="LEGACY_API"),
            sa.Column("file_name", sa.String(300)),
            sa.Column("expected_size", sa.BigInteger()),
            sa.Column("received_size", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("metadata_json", sa.JSON()),
            sa.UniqueConstraint("tenant_id", "session_key", name="uk_file_upload_session_key"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    session_indexes = _indexes(SESSION)
    for name, cols in (
        ("ix_t_file_upload_session_tenant_id", ["tenant_id"]),
        ("ix_t_file_upload_session_file_id", ["file_id"]),
        ("ix_file_upload_session_status", ["tenant_id", "status", "created_at"]),
    ):
        if name not in session_indexes:
            op.create_index(name, SESSION, cols)

    tables = _tables()
    if JOB not in tables:
        op.create_table(
            JOB, *_common_columns(),
            sa.Column("job_type", sa.String(40), nullable=False, server_default="FILE_SCAN"),
            sa.Column("file_id", sa.BigInteger()),
            sa.Column("dedupe_key", sa.String(160), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("available_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("locked_at", sa.DateTime()),
            sa.Column("locked_by", sa.String(120)),
            sa.Column("last_error", sa.Text()),
            sa.Column("payload_json", sa.JSON()),
            sa.Column("result_json", sa.JSON()),
            sa.UniqueConstraint("tenant_id", "dedupe_key", name="uk_file_job_dedupe"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    job_indexes = _indexes(JOB)
    for name, cols in (
        ("ix_t_file_job_tenant_id", ["tenant_id"]),
        ("ix_t_file_job_file_id", ["file_id"]),
        ("ix_t_file_job_status", ["status"]),
        ("ix_file_job_claim", ["job_type", "status", "available_at", "locked_at"]),
    ):
        if name not in job_indexes:
            op.create_index(name, JOB, cols)


def downgrade() -> None:
    for table in (JOB, SESSION, SCAN):
        if table in _tables():
            op.drop_table(table)
    if FILE in _tables():
        cols = _columns(FILE)
        indexes = _indexes(FILE)
        for index_name in ("ix_file_object_scan_queue", "ix_t_file_object_scan_status", "ix_t_file_object_scan_required"):
            if index_name in indexes:
                op.drop_index(index_name, table_name=FILE)
        with op.batch_alter_table(FILE) as batch:
            for name in (
                "rejected_at", "available_at", "scanned_at", "scan_last_error", "scan_signature_version",
                "scan_engine_version", "scan_engine", "scan_attempts", "scan_status", "scan_required",
                "upload_source", "storage_zone", "storage_backend",
            ):
                if name in cols:
                    batch.drop_column(name)
