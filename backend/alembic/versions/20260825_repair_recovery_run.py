"""Repair databases stamped past the recovery evidence migration.

Revision ID: 20260825_repair_recovery_run
Revises: 20260822_pr191_w7_main_merge

Some development databases were stamped at the merged head without actually
creating ``t_recovery_run``. The application must fail closed while rolling
out, and this forward-only repair restores the missing machine-evidence store.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_repair_recovery_run"
down_revision = "20260822_pr191_w7_main_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("t_recovery_run"):
        return

    op.create_table(
        "t_recovery_run",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("run_type", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="MACHINE"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("backup_set_id", sa.String(length=160), nullable=True),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=True),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=True),
        sa.Column("runner_id", sa.String(length=160), nullable=True),
        sa.Column("rpo_seconds", sa.BigInteger(), nullable=True),
        sa.Column("rto_seconds", sa.BigInteger(), nullable=True),
        sa.Column("target_rpo_seconds", sa.BigInteger(), nullable=True),
        sa.Column("target_rto_seconds", sa.BigInteger(), nullable=True),
        sa.Column("assertions_json", sa.JSON(), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("run_id", name="uk_recovery_run_id"),
        sa.UniqueConstraint("evidence_sha256", name="uk_recovery_run_evidence_sha"),
    )
    op.create_index("ix_recovery_run_run_type", "t_recovery_run", ["run_type"], unique=False)
    op.create_index("ix_recovery_run_status", "t_recovery_run", ["status"], unique=False)
    op.create_index("ix_recovery_run_backup_set_id", "t_recovery_run", ["backup_set_id"], unique=False)
    op.create_index("ix_recovery_run_finished_at", "t_recovery_run", ["finished_at"], unique=False)


def downgrade() -> None:
    # This revision repairs drift for a table owned by the earlier canonical
    # migration. Downgrading the repair must not delete machine evidence.
    pass
