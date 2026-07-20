"""Business relation installation ledger.

Revision ID: 0105_business_relations
Revises: 0104_national_standards
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0105_business_relations"
down_revision = "0104_national_standards"
branch_labels = None
depends_on = None


def _common():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    op.create_table(
        "t_system_business_relation_batch", *_common(),
        sa.Column("batch_no", sa.String(60), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("source_import_batch_no", sa.String(60), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("candidates_json", sa.JSON(), nullable=False),
        sa.Column("decisions_json", sa.JSON(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime()),
        sa.Column("applied_at", sa.DateTime()),
        sa.Column("rolled_back_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "batch_no", name="uk_sys_relation_batch_no"),
    )
    op.create_index("ix_t_system_business_relation_batch_tenant_id", "t_system_business_relation_batch", ["tenant_id"])
    op.create_index("ix_t_system_business_relation_batch_project_id", "t_system_business_relation_batch", ["project_id"])
    op.create_index("ix_t_system_business_relation_batch_source_import_batch_no", "t_system_business_relation_batch", ["source_import_batch_no"])
    op.create_index("ix_t_system_business_relation_batch_status", "t_system_business_relation_batch", ["status"])

    op.create_table(
        "t_system_business_relation_install_item", *_common(),
        sa.Column("relation_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("relation_key", sa.String(64), nullable=False),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("subject_ref", sa.String(100), nullable=False),
        sa.Column("object_ref", sa.String(120), nullable=False),
        sa.Column("context_ref", sa.String(120)),
        sa.Column("target_table", sa.String(80), nullable=False),
        sa.Column("target_row_id", sa.BigInteger(), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=False),
        sa.Column("after_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.Column("rolled_back_at", sa.DateTime()),
        sa.Column("rollback_reason", sa.String(500)),
        sa.UniqueConstraint("tenant_id", "project_id", "relation_key", name="uk_sys_relation_install_key"),
    )
    op.create_index("ix_t_system_business_relation_install_item_tenant_id", "t_system_business_relation_install_item", ["tenant_id"])
    op.create_index("ix_t_system_business_relation_install_item_relation_batch_id", "t_system_business_relation_install_item", ["relation_batch_id"])
    op.create_index("ix_t_system_business_relation_install_item_project_id", "t_system_business_relation_install_item", ["project_id"])
    op.create_index("ix_t_system_business_relation_install_item_relation_type", "t_system_business_relation_install_item", ["relation_type"])
    op.create_index("ix_t_system_business_relation_install_item_status", "t_system_business_relation_install_item", ["status"])


def downgrade() -> None:
    op.drop_table("t_system_business_relation_install_item")
    op.drop_table("t_system_business_relation_batch")
