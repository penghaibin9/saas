"""Add the PLAT-A federated integrity exception read model.

Revision ID: 20260829_plat_a_integrity
Revises: 20260829_pr236_main_merge
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260829_plat_a_integrity"
down_revision = "20260829_pr236_main_merge"
branch_labels = None
depends_on = None

assert len(revision) <= 32


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("t_integrity_exception"):
        return
    op.create_table(
        "t_integrity_exception",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("exception_type", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="OPEN"),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="HIGH"),
        sa.Column("detector_code", sa.String(length=64), nullable=False),
        sa.Column("detector_version", sa.String(length=32), nullable=False, server_default="V1"),
        sa.Column("module_code", sa.String(length=64), nullable=True),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.String(length=80), nullable=False),
        sa.Column("manifest_id", sa.BigInteger(), nullable=True),
        sa.Column("file_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_detected_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_detected_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("ignored_at", sa.DateTime(), nullable=True),
        sa.Column("ignored_by", sa.BigInteger(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "fingerprint", name="uk_integrity_exception_fingerprint"),
    )
    op.create_index("ix_t_integrity_exception_tenant_id", "t_integrity_exception", ["tenant_id"])
    op.create_index("ix_t_integrity_exception_exception_type", "t_integrity_exception", ["exception_type"])
    op.create_index("ix_t_integrity_exception_status", "t_integrity_exception", ["status"])
    op.create_index("ix_t_integrity_exception_detector_code", "t_integrity_exception", ["detector_code"])
    op.create_index("ix_t_integrity_exception_module_code", "t_integrity_exception", ["module_code"])
    op.create_index("ix_t_integrity_exception_subject_id", "t_integrity_exception", ["subject_id"])
    op.create_index("ix_t_integrity_exception_manifest_id", "t_integrity_exception", ["manifest_id"])
    op.create_index("ix_t_integrity_exception_file_id", "t_integrity_exception", ["file_id"])
    op.create_index(
        "ix_integrity_exception_queue", "t_integrity_exception",
        ["tenant_id", "status", "severity", "id"],
    )
    op.create_index(
        "ix_integrity_exception_subject", "t_integrity_exception",
        ["tenant_id", "module_code", "subject_type", "subject_id", "id"],
    )
    op.create_index(
        "ix_integrity_exception_detector", "t_integrity_exception",
        ["tenant_id", "detector_code", "last_detected_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("t_integrity_exception")
