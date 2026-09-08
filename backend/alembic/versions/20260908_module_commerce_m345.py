"""M3-M5 module-commerce lifecycle, cancellation and governed exit control facts.

Revision ID: 20260908_module_commerce_m345
Revises: 20260908_module_commerce_m12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260908_module_commerce_m345"
down_revision = "20260908_module_commerce_m12"
branch_labels = None
depends_on = None


def _common_columns():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    op.create_table("t_tenant_module_cancellation_plan",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False), sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False), sa.Column("module_key", sa.String(64), nullable=False),
        sa.Column("module_generation", sa.BigInteger(), nullable=False), sa.Column("status", sa.String(24), nullable=False, server_default="SCHEDULED"),
        sa.Column("effective_at", sa.DateTime(), nullable=False), sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("requested_by", sa.BigInteger(), nullable=True), sa.Column("requested_at", sa.DateTime(), nullable=False), sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        *_common_columns(), sa.ForeignKeyConstraint(["source_id"], ["t_tenant_module_subscription_source.id"]), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "source_id", name="uk_tenant_module_cancel_source"))
    op.create_index("ix_t_tenant_module_cancellation_plan_tenant_id", "t_tenant_module_cancellation_plan", ["tenant_id"])
    op.create_index("ix_t_tenant_module_cancellation_plan_source_id", "t_tenant_module_cancellation_plan", ["source_id"])
    op.create_index("ix_t_tenant_module_cancellation_plan_module_key", "t_tenant_module_cancellation_plan", ["module_key"])
    op.create_index("ix_t_tenant_module_cancellation_plan_effective_at", "t_tenant_module_cancellation_plan", ["effective_at"])
    op.create_index("ix_module_offboard_cancel_due", "t_tenant_module_cancellation_plan", ["status", "effective_at", "tenant_id", "id"])

    op.create_table("t_tenant_module_offboarding_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False), sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("module_key", sa.String(64), nullable=False), sa.Column("module_generation", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="REQUESTED"), sa.Column("expected_lifecycle_version", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False), sa.Column("requested_by", sa.BigInteger(), nullable=True), sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False), sa.Column("retention_policy_version", sa.String(64), nullable=False), sa.Column("retention_until", sa.DateTime(), nullable=True),
        sa.Column("scope_hash", sa.String(64), nullable=False), sa.Column("export_job_id", sa.BigInteger(), nullable=True), sa.Column("manifest_id", sa.BigInteger(), nullable=True),
        sa.Column("export_file_id", sa.BigInteger(), nullable=True), sa.Column("acceptance_ref", sa.String(160), nullable=True), sa.Column("accepted_by", sa.BigInteger(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True), sa.Column("irreversible_started_at", sa.DateTime(), nullable=True), sa.Column("last_completed_step", sa.String(40), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True), sa.Column("last_error", sa.Text(), nullable=True), *_common_columns(), sa.PrimaryKeyConstraint("id"))
    for name, cols in (("ix_t_tenant_module_offboarding_job_tenant_id", ["tenant_id"]),("ix_t_tenant_module_offboarding_job_module_key", ["module_key"]),("ix_t_tenant_module_offboarding_job_state", ["state"]),("ix_t_tenant_module_offboarding_job_scope_hash", ["scope_hash"]),("ix_t_tenant_module_offboarding_job_export_job_id", ["export_job_id"]),("ix_t_tenant_module_offboarding_job_manifest_id", ["manifest_id"]),("ix_t_tenant_module_offboarding_job_export_file_id", ["export_file_id"]),("ix_module_offboard_active", ["tenant_id", "module_key", "state", "id"]),("ix_module_offboard_state", ["state", "created_at", "id"])):
        op.create_index(name, "t_tenant_module_offboarding_job", cols)

    op.create_table("t_tenant_module_offboarding_step",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False), sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False), sa.Column("step_code", sa.String(40), nullable=False), sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("result_json", sa.JSON(), nullable=True), sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True), sa.Column("finished_at", sa.DateTime(), nullable=True), *_common_columns(),
        sa.ForeignKeyConstraint(["job_id"], ["t_tenant_module_offboarding_job.id"]), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "step_code", name="uk_module_offboard_step"))
    op.create_index("ix_t_tenant_module_offboarding_step_tenant_id", "t_tenant_module_offboarding_step", ["tenant_id"])
    op.create_index("ix_t_tenant_module_offboarding_step_job_id", "t_tenant_module_offboarding_step", ["job_id"])
    op.create_index("ix_module_offboard_step_job", "t_tenant_module_offboarding_step", ["tenant_id", "job_id", "step_code"])


def downgrade() -> None:
    op.drop_table("t_tenant_module_offboarding_step"); op.drop_table("t_tenant_module_offboarding_job"); op.drop_table("t_tenant_module_cancellation_plan")
