"""M8 renewal follow-up link to existing customer-success RenewalTask.

Revision ID: 20260909_module_commerce_m8_renewal
Revises: 20260909_module_commerce_m8_operations
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
revision="20260909_module_commerce_m8_renewal"; down_revision="20260909_module_commerce_m8_operations"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("t_commercial_renewal_followup_link",
        sa.Column("id",sa.BigInteger(),autoincrement=True,nullable=False),sa.Column("tenant_id",sa.BigInteger(),nullable=False),
        sa.Column("source_id",sa.BigInteger(),nullable=False),sa.Column("renewal_task_id",sa.BigInteger(),nullable=False),
        sa.Column("module_key",sa.String(64),nullable=False),sa.Column("module_generation",sa.BigInteger(),nullable=False),
        sa.Column("source_ends_at_snapshot",sa.DateTime(),nullable=False),sa.Column("source_status_snapshot",sa.String(24),nullable=False),
        sa.Column("linked_at",sa.DateTime(),nullable=False),sa.Column("linked_by",sa.BigInteger(),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("created_by",sa.BigInteger(),nullable=True),
        sa.Column("updated_at",sa.DateTime(),nullable=False),sa.Column("updated_by",sa.BigInteger(),nullable=True),
        sa.Column("is_deleted",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("version",sa.Integer(),nullable=False,server_default="0"),
        sa.ForeignKeyConstraint(["source_id"],["t_tenant_module_subscription_source.id"]),sa.ForeignKeyConstraint(["renewal_task_id"],["t_renewal_task.id"]),
        sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("tenant_id","source_id",name="uk_commercial_renewal_source"),
        sa.UniqueConstraint("tenant_id","renewal_task_id",name="uk_commercial_renewal_task"))
    op.create_index("ix_t_commercial_renewal_followup_link_tenant_id","t_commercial_renewal_followup_link",["tenant_id"])
    op.create_index("ix_t_commercial_renewal_followup_link_source_id","t_commercial_renewal_followup_link",["source_id"])
    op.create_index("ix_t_commercial_renewal_followup_link_renewal_task_id","t_commercial_renewal_followup_link",["renewal_task_id"])
    op.create_index("ix_commercial_renewal_followup_due","t_commercial_renewal_followup_link",["tenant_id","source_ends_at_snapshot","id"])

def downgrade(): op.drop_table("t_commercial_renewal_followup_link")
