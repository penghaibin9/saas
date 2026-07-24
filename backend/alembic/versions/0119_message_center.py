"""消息中心：发布单 / 受众 / 附件 / 事件 outbox + 演进个人消息列

Revision ID: 0119_message_center
Revises: 0118_system_json_doc
Create Date: 2026-07-23

纯增量：只新增表/列/索引，不删除旧 receiver_id 与旧接口字段。
幂等：表/列/索引已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0119_message_center"
down_revision = "0118_system_json_doc"
branch_labels = None
depends_on = None

MSG = "t_unified_message"


def _tables(bind) -> set[str]:
    return set(inspect(bind).get_table_names())


def _cols(bind, table: str) -> set[str]:
    if table not in _tables(bind):
        return set()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    if table not in _tables(bind):
        return set()
    return {i["name"] for i in inspect(bind).get_indexes(table)}


def _uniques(bind, table: str) -> set[str]:
    if table not in _tables(bind):
        return set()
    return {u["name"] for u in inspect(bind).get_unique_constraints(table)}


def _add_col(bind, table: str, col: sa.Column) -> None:
    if col.name not in _cols(bind, table):
        op.add_column(table, col)


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)

    # ── 演进 t_unified_message ──
    if MSG in tables:
        _add_col(bind, MSG, sa.Column("campaign_id", sa.BigInteger(), nullable=True))
        _add_col(bind, MSG, sa.Column("receiver_user_id", sa.BigInteger(), nullable=True))
        _add_col(bind, MSG, sa.Column("receiver_type", sa.String(20), nullable=True))
        _add_col(bind, MSG, sa.Column(
            "receiver_context_key", sa.String(64), nullable=False, server_default="GLOBAL"))
        _add_col(bind, MSG, sa.Column("priority", sa.String(20), nullable=True))
        _add_col(bind, MSG, sa.Column("category", sa.String(30), nullable=True))
        _add_col(bind, MSG, sa.Column("delivered_at", sa.DateTime(), nullable=True))
        _add_col(bind, MSG, sa.Column("ack_at", sa.DateTime(), nullable=True))
        _add_col(bind, MSG, sa.Column(
            "require_ack", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        _add_col(bind, MSG, sa.Column("action_key", sa.String(80), nullable=True))
        _add_col(bind, MSG, sa.Column("action_params_json", sa.JSON(), nullable=True))
        _add_col(bind, MSG, sa.Column("expire_at", sa.DateTime(), nullable=True))
        _add_col(bind, MSG, sa.Column(
            "content_version", sa.Integer(), nullable=False, server_default="1"))
        _add_col(bind, MSG, sa.Column("delivery_status", sa.String(20), nullable=True))
        _add_col(bind, MSG, sa.Column("rendered_title", sa.String(500), nullable=True))
        _add_col(bind, MSG, sa.Column("rendered_content_plain", sa.Text(), nullable=True))
        _add_col(bind, MSG, sa.Column("sender_org_name_snapshot", sa.String(200), nullable=True))
        _add_col(bind, MSG, sa.Column(
            "pinned", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        _add_col(bind, MSG, sa.Column("withdrawn_at", sa.DateTime(), nullable=True))
        _add_col(bind, MSG, sa.Column("withdraw_reason", sa.String(500), nullable=True))

        idxs = _indexes(bind, MSG)
        if "ix_msg_tenant_user_ctx_status_created" not in idxs:
            op.create_index(
                "ix_msg_tenant_user_ctx_status_created", MSG,
                ["tenant_id", "receiver_user_id", "receiver_context_key", "status", "created_at", "id"],
            )
        if "ix_t_unified_message_campaign_id" not in idxs:
            op.create_index("ix_t_unified_message_campaign_id", MSG, ["campaign_id"])
        if "ix_t_unified_message_receiver_user_id" not in idxs:
            op.create_index("ix_t_unified_message_receiver_user_id", MSG, ["receiver_user_id"])

        uqs = _uniques(bind, MSG)
        # 部分方言 get_unique_constraints 可能拿不到名；再用索引名兜底
        if "uk_msg_campaign_receiver_ctx" not in uqs and "uk_msg_campaign_receiver_ctx" not in idxs:
            try:
                op.create_unique_constraint(
                    "uk_msg_campaign_receiver_ctx", MSG,
                    ["tenant_id", "campaign_id", "receiver_user_id", "receiver_context_key"],
                )
            except Exception:
                # SQLite / 已存在时跳过，不阻断升级
                pass

    # ── t_message_campaign ──
    if "t_message_campaign" not in tables:
        op.create_table(
            "t_message_campaign",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("content_plain", sa.Text(), nullable=False),
            sa.Column("content_html", sa.Text(), nullable=True),
            sa.Column("summary", sa.String(200), nullable=True),
            sa.Column("category", sa.String(30), nullable=False, server_default="ANNOUNCEMENT"),
            sa.Column("priority", sa.String(20), nullable=False, server_default="NORMAL"),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("source_kind", sa.String(20), nullable=False, server_default="HUMAN"),
            sa.Column("source_module", sa.String(50), nullable=True),
            sa.Column("source_biz_type", sa.String(50), nullable=True),
            sa.Column("source_biz_id", sa.BigInteger(), nullable=True),
            sa.Column("content_mode", sa.String(20), nullable=False, server_default="SHARED"),
            sa.Column("template_id", sa.BigInteger(), nullable=True),
            sa.Column("template_version", sa.String(30), nullable=True),
            sa.Column("sender_user_id", sa.BigInteger(), nullable=False),
            sa.Column("sender_context_id", sa.String(64), nullable=True),
            sa.Column("sender_org_id", sa.BigInteger(), nullable=True),
            sa.Column("sender_name_snapshot", sa.String(100), nullable=True),
            sa.Column("sender_role_snapshot", sa.String(64), nullable=True),
            sa.Column("org_name_snapshot", sa.String(200), nullable=True),
            sa.Column("publish_mode", sa.String(20), nullable=False, server_default="IMMEDIATE"),
            sa.Column("scheduled_at", sa.DateTime(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("effective_at", sa.DateTime(), nullable=True),
            sa.Column("expire_at", sa.DateTime(), nullable=True),
            sa.Column("require_ack", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("emergency", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("action_key", sa.String(80), nullable=True),
            sa.Column("action_params_json", sa.JSON(), nullable=True),
            sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
            sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("read_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ack_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("idempotency_key", sa.String(80), nullable=True),
            sa.Column("audience_fingerprint", sa.String(80), nullable=True),
            sa.Column("supersedes_campaign_id", sa.BigInteger(), nullable=True),
            sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
            sa.Column("withdrawn_by", sa.BigInteger(), nullable=True),
            sa.Column("withdraw_reason", sa.String(500), nullable=True),
            sa.Column("channels_json", sa.JSON(), nullable=True),
            sa.Column("remark", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_campaign_tenant_idem"),
        )
        op.create_index(
            "ix_campaign_tenant_status_sched", "t_message_campaign",
            ["tenant_id", "status", "scheduled_at", "id"])
        op.create_index(
            "ix_campaign_tenant_org_created", "t_message_campaign",
            ["tenant_id", "sender_org_id", "created_at", "id"])
        op.create_index("ix_t_message_campaign_sender_user_id", "t_message_campaign", ["sender_user_id"])

    # ── t_message_audience ──
    if "t_message_audience" not in _tables(bind):
        op.create_table(
            "t_message_audience",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("campaign_id", sa.BigInteger(), nullable=False),
            sa.Column("audience_type", sa.String(30), nullable=False),
            sa.Column("include_or_exclude", sa.String(10), nullable=False, server_default="INCLUDE"),
            sa.Column("target_id", sa.BigInteger(), nullable=True),
            sa.Column("target_code", sa.String(64), nullable=True),
            sa.Column("include_children", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("rule_json", sa.JSON(), nullable=True),
            sa.Column("rule_version", sa.String(20), nullable=False, server_default="1"),
            sa.Column("resolved_count", sa.Integer(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index(
            "ix_audience_campaign", "t_message_audience",
            ["tenant_id", "campaign_id", "id"])
        op.create_index("ix_t_message_audience_campaign_id", "t_message_audience", ["campaign_id"])

    # ── t_message_attachment ──
    if "t_message_attachment" not in _tables(bind):
        op.create_table(
            "t_message_attachment",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("campaign_id", sa.BigInteger(), nullable=False),
            sa.Column("file_id", sa.BigInteger(), nullable=False),
            sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("file_name_snapshot", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index(
            "ix_msg_attach_campaign", "t_message_attachment",
            ["tenant_id", "campaign_id", "sort_no"])

    # ── t_message_event_outbox ──
    if "t_message_event_outbox" not in _tables(bind):
        op.create_table(
            "t_message_event_outbox",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("event_code", sa.String(80), nullable=False),
            sa.Column("source_module", sa.String(50), nullable=False),
            sa.Column("source_biz_type", sa.String(50), nullable=False),
            sa.Column("source_biz_id", sa.BigInteger(), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column("recipient_refs_json", sa.JSON(), nullable=True),
            sa.Column("dedup_key", sa.String(120), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_code", sa.String(80), nullable=True),
            sa.Column("locked_by", sa.String(80), nullable=True),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("campaign_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "dedup_key", name="uk_outbox_tenant_dedup"),
        )
        op.create_index(
            "ix_outbox_status_retry", "t_message_event_outbox",
            ["status", "next_retry_at", "id"])
        op.create_index(
            "ix_t_message_event_outbox_event_code", "t_message_event_outbox", ["event_code"])


def downgrade() -> None:
    """回滚：仅删新增表；演进列保留（避免已产生消息事实丢失）。"""
    bind = op.get_bind()
    for t in (
        "t_message_event_outbox",
        "t_message_attachment",
        "t_message_audience",
        "t_message_campaign",
    ):
        if t in _tables(bind):
            op.drop_table(t)
    # 个人消息演进列按设计不在降级时物理删除
    _ = text  # keep import used for linters that track text()
