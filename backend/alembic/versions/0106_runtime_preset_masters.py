"""Workflow, role workbench and notification preset master tables.

Revision ID: 0106_runtime_presets
Revises: 0105_business_relations

守卫说明：0001_init_core_tables 是 metadata.create_all 活基线——全新库跑链时
会先按当前模型建出本迁移目标表，故 create_table / create_index / add_column
必须幂等（同 0142_gd_excellent_delay_workflows 约定）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0106_runtime_presets"
down_revision = "0105_business_relations"
branch_labels = None
depends_on = None


def _table_names():
    return set(inspect(op.get_bind()).get_table_names())


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return set()
    return {idx["name"] for idx in inspect(bind).get_indexes(table)}


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return set()
    return {col["name"] for col in inspect(bind).get_columns(table)}


def _unique_constraint_names(table: str) -> set[str]:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return set()
    return {uc["name"] for uc in inspect(bind).get_unique_constraints(table)}


def _common():
    return [sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0")]


def upgrade() -> None:
    names = _table_names()
    if "t_workflow_definition" not in names:
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
    workflow_definition_indexes = _index_names("t_workflow_definition")
    for column in ("tenant_id", "status", "installed_project_id"):
        index_name = f"ix_t_workflow_definition_{column}"
        if index_name not in workflow_definition_indexes:
            op.create_index(index_name, "t_workflow_definition", [column])

    names = _table_names()
    if "t_workflow_node_definition" not in names:
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
    workflow_node_indexes = _index_names("t_workflow_node_definition")
    for column in ("tenant_id", "workflow_definition_id"):
        index_name = f"ix_t_workflow_node_definition_{column}"
        if index_name not in workflow_node_indexes:
            op.create_index(index_name, "t_workflow_node_definition", [column])

    names = _table_names()
    if "t_role_workbench_config" not in names:
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
    role_workbench_indexes = _index_names("t_role_workbench_config")
    for column in ("tenant_id", "installed_project_id"):
        index_name = f"ix_t_role_workbench_config_{column}"
        if index_name not in role_workbench_indexes:
            op.create_index(index_name, "t_role_workbench_config", [column])

    notification_columns = _column_names("t_notification_template")
    notification_indexes = _index_names("t_notification_template")
    notification_uniques = _unique_constraint_names("t_notification_template")
    with op.batch_alter_table("t_notification_template") as batch:
        if "event_code" not in notification_columns:
            batch.add_column(sa.Column("event_code", sa.String(80)))
        if "template_version" not in notification_columns:
            batch.add_column(sa.Column("template_version", sa.String(30), nullable=False, server_default="2026.1"))
        if "receiver_rule_json" not in notification_columns:
            batch.add_column(sa.Column("receiver_rule_json", sa.JSON()))
        if "variables_json" not in notification_columns:
            batch.add_column(sa.Column("variables_json", sa.JSON()))
        if "deep_link" not in notification_columns:
            batch.add_column(sa.Column("deep_link", sa.String(500)))
        if "locked_fields_json" not in notification_columns:
            batch.add_column(sa.Column("locked_fields_json", sa.JSON()))
        if "source_profile" not in notification_columns:
            batch.add_column(sa.Column("source_profile", sa.String(50)))
        if "installed_project_id" not in notification_columns:
            batch.add_column(sa.Column("installed_project_id", sa.BigInteger()))
        if "uk_notification_template_channel" not in notification_uniques:
            batch.create_unique_constraint(
                "uk_notification_template_channel", ["tenant_id", "template_code", "channel"])
        if "ix_t_notification_template_event_code" not in notification_indexes:
            batch.create_index("ix_t_notification_template_event_code", ["event_code"])
        if "ix_t_notification_template_installed_project_id" not in notification_indexes:
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
