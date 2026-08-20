"""Control-plane P0: durable authentication risk and captcha state.

Revision ID: 20260820_ctrl_auth_risk
Revises: 20260818_acad_bc_final
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260820_ctrl_auth_risk"
down_revision = "20260818_acad_bc_final"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_auth_risk_state",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("risk_type", sa.String(length=40), nullable=False),
        sa.Column("risk_key_hash", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("risk_type", "risk_key_hash", name="uk_auth_risk_type_key"),
    )
    op.create_index("ix_auth_risk_state_tenant_id", "t_auth_risk_state", ["tenant_id"], unique=False)
    op.create_index("ix_auth_risk_state_locked_until", "t_auth_risk_state", ["locked_until"], unique=False)
    op.create_index("ix_auth_risk_state_expires_at", "t_auth_risk_state", ["expires_at"], unique=False)
    op.create_index("ix_auth_risk_expiry", "t_auth_risk_state", ["risk_type", "expires_at", "id"], unique=False)
    op.create_index("ix_auth_risk_tenant_lock", "t_auth_risk_state", ["tenant_id", "locked_until", "id"], unique=False)

    op.create_table(
        "t_auth_challenge_state",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("challenge_id_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("challenge_id_hash", name="uq_auth_challenge_state_challenge_id_hash"),
    )
    op.create_index("ix_auth_challenge_state_challenge_id_hash", "t_auth_challenge_state", ["challenge_id_hash"], unique=True)
    op.create_index("ix_auth_challenge_state_expires_at", "t_auth_challenge_state", ["expires_at"], unique=False)
    op.create_index("ix_auth_challenge_state_consumed_at", "t_auth_challenge_state", ["consumed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_challenge_state_consumed_at", table_name="t_auth_challenge_state")
    op.drop_index("ix_auth_challenge_state_expires_at", table_name="t_auth_challenge_state")
    op.drop_index("ix_auth_challenge_state_challenge_id_hash", table_name="t_auth_challenge_state")
    op.drop_table("t_auth_challenge_state")

    op.drop_index("ix_auth_risk_tenant_lock", table_name="t_auth_risk_state")
    op.drop_index("ix_auth_risk_expiry", table_name="t_auth_risk_state")
    op.drop_index("ix_auth_risk_state_expires_at", table_name="t_auth_risk_state")
    op.drop_index("ix_auth_risk_state_locked_until", table_name="t_auth_risk_state")
    op.drop_index("ix_auth_risk_state_tenant_id", table_name="t_auth_risk_state")
    op.drop_table("t_auth_risk_state")
