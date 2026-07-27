"""Workflow, role workbench and notification preset master tables.

Revision ID: 0106_runtime_presets
Revises: 0105_business_relations
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0106_runtime_presets"
down_revision = "0105_business_relations"
branch_labels = None
depends_on = None


def _common():
    return [sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0")]


def upgrade() -> None:
    op.create_table("t_workflow_definition", *_common(),
        sa.Column("workflow_code", sa.String(100), nullable=False),
        sa.Column("workflow_name", sa.String(200), nullable=False),
        sa.Column("source_module", sa.String(60), nullable=False),
        sa.Column("source_biz_type", sa.String(100), nullable=False),
        sa.Column("definition_version", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("policy_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("policy_confirmed_by", sa.BigInteger()), sa.Column("policy_confirmed_at", sa.DateTime()),
        sa.Column("timeout_hours", sa.Integer(), nullable=False),
        sa.Column("allow_transfer", sa.Boolean(), nullable=False),
        sa.Column("allow_reject", sa.Boolean(), nullable=False),
        sa.Column("allow_withdraw", sa.Boolean(), nullable=False),
        sa.Column("starter_role_codes_json", sa.JSON(), nullable=False),
        sa.Column("cc_role_codes_json", sa.JSON(), nullable=False),
        sa.Column("policy_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("source_profile", sa.String(50), nullable=False),
        sa.Column("installed_project_id", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.UniqueConstraint("tenant_id", "workflow_code", name="uk_workflow_definition_code"))
    for column in ("tenant_id", "status", "installed_project_id"):
        op.create_index(f"ix_t_workflow_definition_{column}", "t_workflow_definition", [column])
    op.create_table("t_workflow_node_definition", *_common(),
        sa.Column("workflow_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("node_code", sa.String(100), nullable=False),
        sa.Column("node_name", sa.String(150), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("approver_role_code", sa.String(50), nullable=False),
        sa.Column("assignee_strategy", sa.String(40), nullable=False),
        sa.Column("data_scope_code", sa.String(40), nullable=False),
        sa.Column("timeout_hours", sa.Integer(), nullable=False),
        sa.Column("condition_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("tenant_id", "workflow_definition_id", "node_code",
                            name="uk_workflow_node_definition_code"))
    for column in ("tenant_id", "workflow_definition_id"):
        op.create_index(f"ix_t_workflow_node_definition_{column}", "t_workflow_node_definition", [column])
    op.create_table("t_role_workbench_config", *_common(),
        sa.Column("role_code", sa.String(50), nullable=False),
        sa.Column("title", sa.String(120), nullable=False), sa.Column("subtitle", sa.String(300)),
        sa.Column("layout_code", sa.String(40), nullable=False),
        sa.Column("card_keys_json", sa.JSON(), nullable=False),
        sa.Column("quick_entries_json", sa.JSON(), nullable=False),
        sa.Column("alert_keys_json", sa.JSON(), nullable=False),
        sa.Column("source_profile", sa.String(50), nullable=False),
        sa.Column("installed_project_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("tenant_id", "role_code", name="uk_role_workbench_role"))
    for column in ("tenant_id", "installed_project_id"):
        op.create_index(f"ix_t_role_workbench_config_{column}", "t_role_workbench_config", [column])

    with op.batch_alter_table("t_notification_template") as batch:
        batch.add_column(sa.Column("event_code", sa.String(80)))
        batch.add_column(sa.Column("template_version", sa.String(30), nullable=False, server_default="2026.1"))
        batch.add_column(sa.Column("receiver_rule_json", sa.JSON()))
        batch.add_column(sa.Column("variables_json", sa.JSON()))
        batch.add_column(sa.Column("deep_link", sa.String(500)))
        batch.add_column(sa.Column("locked_fields_json", sa.JSON()))
        batch.add_column(sa.Column("source_profile", sa.String(50)))
        batch.add_column(sa.Column("installed_project_id", sa.BigInteger()))
        batch.create_unique_constraint("uk_notification_template_channel", ["tenant_id", "template_code", "channel"])
        batch.create_index("ix_t_notification_template_event_code", ["event_code"])
        batch.create_index("ix_t_notification_template_installed_project_id", ["installed_project_id"])


def downgrade() -> None:
    with op.batch_alter_table("t_notification_template") as batch:
        batch.drop_constraint("uk_notification_template_channel", type_="unique")
        for name in ("installed_project_id", "event_code"):
            batch.drop_index(f"ix_t_notification_template_{name}")
        for name in ("installed_project_id", "source_profile", "locked_fields_json", "deep_link",
                     "variables_json", "receiver_rule_json", "template_version", "event_code"):
            batch.drop_column(name)
    op.drop_table("t_role_workbench_config")
    op.drop_table("t_workflow_node_definition")
    op.drop_table("t_workflow_definition")
