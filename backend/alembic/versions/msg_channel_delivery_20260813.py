"""add durable message channel delivery queue

Revision ID: msg_channel_delivery_20260813
Revises: 20260810_grad_audit_text
"""
from alembic import op
import sqlalchemy as sa

revision = "msg_channel_delivery_20260813"
down_revision = "20260810_grad_audit_text"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "t_message_channel_delivery",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("campaign_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("receiver_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by", sa.String(80), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_code", sa.String(80), nullable=True),
        sa.Column("last_error_message_safe", sa.String(200), nullable=True),
        sa.Column("provider_request_id", sa.String(120), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id","campaign_id","channel","receiver_user_id",name="uk_msg_channel_delivery_receiver"),
    )
    op.create_index("ix_msg_channel_delivery_claim","t_message_channel_delivery",["tenant_id","status","next_retry_at","id"])
    op.create_index("ix_msg_channel_delivery_lease","t_message_channel_delivery",["tenant_id","status","lease_expires_at","id"])
    op.create_index("ix_msg_channel_delivery_campaign","t_message_channel_delivery",["tenant_id","campaign_id","channel","status"])
    op.create_index(op.f("ix_t_message_channel_delivery_campaign_id"),"t_message_channel_delivery",["campaign_id"])
    op.create_index(op.f("ix_t_message_channel_delivery_receiver_user_id"),"t_message_channel_delivery",["receiver_user_id"])
    op.create_index(op.f("ix_t_message_channel_delivery_tenant_id"),"t_message_channel_delivery",["tenant_id"])

def downgrade():
    op.drop_table("t_message_channel_delivery")
