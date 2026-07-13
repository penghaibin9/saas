"""Graduation production integrity hashes and composite query indexes.

Revision ID: 0045_gd_production_integrity
Revises: 0044_13a_psy_referral
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0045_gd_production_integrity"
down_revision = "0044_13a_psy_referral"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table)}


def _add_index(bind, name: str, table: str, columns: list[str]) -> None:
    if _columns(bind, table) and name not in _indexes(bind, table):
        op.create_index(name, table, columns, unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    if _columns(bind, "t_gd_grade") and "source_snapshot_hash" not in _columns(bind, "t_gd_grade"):
        op.add_column("t_gd_grade", sa.Column("source_snapshot_hash", sa.String(64), nullable=True))
    if _columns(bind, "t_gd_archive_record") and "manifest_hash" not in _columns(bind, "t_gd_archive_record"):
        op.add_column("t_gd_archive_record", sa.Column("manifest_hash", sa.String(64), nullable=True))
    audit_columns = _columns(bind, "t_gd_audit_trail")
    if audit_columns and "request_id" not in audit_columns:
        op.add_column("t_gd_audit_trail", sa.Column("request_id", sa.String(64), nullable=True))
    if audit_columns and "request_path" not in audit_columns:
        op.add_column("t_gd_audit_trail", sa.Column("request_path", sa.String(500), nullable=True))
    if audit_columns and "client_ip" not in audit_columns:
        op.add_column("t_gd_audit_trail", sa.Column("client_ip", sa.String(64), nullable=True))

    _add_index(bind, "ix_gd_final_tenant_student_status", "t_gd_final",
               ["tenant_id", "gd_student_id", "status", "is_deleted"])
    _add_index(bind, "ix_gd_review_tenant_student_status", "t_gd_review",
               ["tenant_id", "gd_student_id", "status", "is_deleted"])
    _add_index(bind, "ix_gd_plag_tenant_final_status", "t_gd_plagiarism",
               ["tenant_id", "gd_final_id", "status", "is_deleted"])
    _add_index(bind, "ix_gd_archive_tenant_status", "t_gd_archive_record",
               ["tenant_id", "status", "is_deleted"])
    _add_index(bind, "ix_gd_choice_round_status", "t_gd_topic_choice",
               ["tenant_id", "round_id", "status", "is_deleted"])
    _add_index(bind, "ix_gd_student_tenant_stage_active", "t_gd_student",
               ["tenant_id", "stage", "record_status", "is_deleted"])
    _add_index(bind, "ix_gd_audit_request_id", "t_gd_audit_trail", ["tenant_id", "request_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for name, table in (
        ("ix_gd_audit_request_id", "t_gd_audit_trail"),
        ("ix_gd_student_tenant_stage_active", "t_gd_student"),
        ("ix_gd_choice_round_status", "t_gd_topic_choice"),
        ("ix_gd_archive_tenant_status", "t_gd_archive_record"),
        ("ix_gd_plag_tenant_final_status", "t_gd_plagiarism"),
        ("ix_gd_review_tenant_student_status", "t_gd_review"),
        ("ix_gd_final_tenant_student_status", "t_gd_final"),
    ):
        if name in _indexes(bind, table):
            op.drop_index(name, table_name=table)
    if "manifest_hash" in _columns(bind, "t_gd_archive_record"):
        op.drop_column("t_gd_archive_record", "manifest_hash")
    if "source_snapshot_hash" in _columns(bind, "t_gd_grade"):
        op.drop_column("t_gd_grade", "source_snapshot_hash")
    for column in ("client_ip", "request_path", "request_id"):
        if column in _columns(bind, "t_gd_audit_trail"):
            op.drop_column("t_gd_audit_trail", column)
