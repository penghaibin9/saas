"""学生密码重置短信可靠投递作业。

Revision ID: 20260809_pwreset_sms_job
Revises: 20260808_aa_gpa_policy
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260809_pwreset_sms_job"
down_revision = "20260808_aa_gpa_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_password_reset_sms_job",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("phone_encrypted", sa.String(500), nullable=True),
        sa.Column("code_encrypted", sa.String(500), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by", sa.String(100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("provider_request_id", sa.String(100), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("request_id", name="uk_password_reset_sms_request"),
    )
    op.create_index("ix_password_reset_sms_tenant", "t_password_reset_sms_job", ["tenant_id"])
    op.create_index("ix_password_reset_sms_user", "t_password_reset_sms_job", ["user_id"])
    op.create_index("ix_password_reset_sms_expires", "t_password_reset_sms_job", ["expires_at"])
    op.create_index("ix_password_reset_sms_claim", "t_password_reset_sms_job",
                    ["status", "next_retry_at", "lease_expires_at", "id"])


def downgrade() -> None:
    op.drop_table("t_password_reset_sms_job")
