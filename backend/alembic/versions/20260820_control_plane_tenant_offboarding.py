"""Control-plane P0: tenant offboarding/destruction workflow.

Revision ID: 20260820_ctrl_offboarding
Revises: 20260820_ctrl_recovery
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260820_ctrl_offboarding"
down_revision = "20260820_ctrl_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_tenant_offboarding_job",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("expected_tenant_version", sa.BigInteger(), nullable=False),
        sa.Column("final_export_sha256", sa.String(length=64), nullable=True),
        sa.Column("retention_until", sa.DateTime(), nullable=True),
        sa.Column("legal_hold_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("purge_evidence_sha256", sa.String(length=64), nullable=True),
        sa.Column("preview_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_tenant_offboarding_job_tenant_id", "t_tenant_offboarding_job", ["tenant_id"], unique=False)
    op.create_index("ix_tenant_offboarding_job_state", "t_tenant_offboarding_job", ["state"], unique=False)
    op.create_index("ix_tenant_offboarding_job_retention_until", "t_tenant_offboarding_job", ["retention_until"], unique=False)

    op.create_table(
        "t_tenant_offboarding_step",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("step_code", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("job_id", "step_code", name="uk_tenant_offboarding_step"),
    )
    op.create_index("ix_tenant_offboarding_step_job_id", "t_tenant_offboarding_step", ["job_id"], unique=False)
    op.create_index("ix_tenant_offboarding_step_status", "t_tenant_offboarding_step", ["status"], unique=False)

    op.create_table(
        "t_tenant_tombstone",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_code_hash", sa.String(length=64), nullable=False),
        sa.Column("tenant_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("offboarding_job_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("final_export_sha256", sa.String(length=64), nullable=False),
        sa.Column("purge_evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("purged_at", sa.DateTime(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_tombstone_tenant_id"),
        sa.UniqueConstraint("offboarding_job_id", name="uq_tenant_tombstone_job_id"),
    )
    op.create_index("ix_tenant_tombstone_tenant_id", "t_tenant_tombstone", ["tenant_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenant_tombstone_tenant_id", table_name="t_tenant_tombstone")
    op.drop_table("t_tenant_tombstone")
    op.drop_index("ix_tenant_offboarding_step_status", table_name="t_tenant_offboarding_step")
    op.drop_index("ix_tenant_offboarding_step_job_id", table_name="t_tenant_offboarding_step")
    op.drop_table("t_tenant_offboarding_step")
    op.drop_index("ix_tenant_offboarding_job_retention_until", table_name="t_tenant_offboarding_job")
    op.drop_index("ix_tenant_offboarding_job_state", table_name="t_tenant_offboarding_job")
    op.drop_index("ix_tenant_offboarding_job_tenant_id", table_name="t_tenant_offboarding_job")
    op.drop_table("t_tenant_offboarding_job")
