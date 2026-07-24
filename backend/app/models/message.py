"""消息中心模型（工作台·消息中心）。

表：
- t_unified_message      个人收件记录（演进自旧站内消息）
- t_message_campaign     发布单（控制面）
- t_message_audience     受众规则
- t_message_attachment   附件关联（文件中心 file_id）
- t_message_event_outbox 业务事件投递队列

状态语义（不可混用）：
- 已送达 delivered_at ≠ 已读 read_at/status ≠ 已确认 ack_at ≠ 业务已办理
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class UnifiedMessage(PKMixin, TenantMixin, CommonMixin, Base):
    """t_unified_message 个人收件记录。

    历史字段 receiver_id 暂留兼容（旧写入可能是学籍/教师档案/用户 ID 混装）。
    新写入必须填 receiver_user_id；唯一接收人主键以 user_id 为准。
    """
    __tablename__ = "t_unified_message"
    __table_args__ = (
        Index("ix_msg_tenant_receiver_active_id", "tenant_id", "receiver_id", "is_deleted", "id"),
        Index("ix_msg_tenant_receiver_unread", "tenant_id", "receiver_id", "is_deleted", "status"),
        Index(
            "ix_msg_tenant_user_ctx_status_created",
            "tenant_id", "receiver_user_id", "receiver_context_key", "status", "created_at", "id",
        ),
        UniqueConstraint(
            "tenant_id", "campaign_id", "receiver_user_id", "receiver_context_key",
            name="uk_msg_campaign_receiver_ctx",
        ),
    )

    # ── 兼容旧字段 ──
    receiver_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_module: Mapped[str | None] = mapped_column(String(50))
    source_biz_id: Mapped[int | None] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(String(2000))
    message_type: Mapped[str | None] = mapped_column(
        String(50), comment="ANNOUNCEMENT/BUSINESS/REMINDER/EMERGENCY/SYSTEM/TODO_NOTICE")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="UNREAD", comment="UNREAD/READ")
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))

    # ── 消息中心演进字段 ──
    campaign_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    receiver_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    receiver_type: Mapped[str | None] = mapped_column(
        String(20), comment="STUDENT/STAFF/UNKNOWN")
    receiver_context_key: Mapped[str] = mapped_column(
        String(64), nullable=False, default="GLOBAL", server_default="GLOBAL",
        comment="GLOBAL=个人全局；非空身份键=仅该激活身份可见")
    priority: Mapped[str | None] = mapped_column(
        String(20), comment="NORMAL/IMPORTANT/EMERGENCY")
    category: Mapped[str | None] = mapped_column(
        String(30), comment="ALL/EMERGENCY/ANNOUNCEMENT/BUSINESS/TODO/SYSTEM")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    ack_at: Mapped[datetime | None] = mapped_column(DateTime)
    require_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_key: Mapped[str | None] = mapped_column(String(80))
    action_params_json: Mapped[dict | None] = mapped_column(JSON)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delivery_status: Mapped[str | None] = mapped_column(
        String(20), comment="PENDING/DELIVERED/FAILED")
    rendered_title: Mapped[str | None] = mapped_column(String(500))
    rendered_content_plain: Mapped[str | None] = mapped_column(Text)
    sender_org_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdraw_reason: Mapped[str | None] = mapped_column(String(500))


class MessageCampaign(PKMixin, TenantMixin, CommonMixin, Base):
    """t_message_campaign 发布单（控制面）。"""
    __tablename__ = "t_message_campaign"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_campaign_tenant_idem"),
        Index("ix_campaign_tenant_status_sched", "tenant_id", "status", "scheduled_at", "id"),
        Index("ix_campaign_tenant_org_created", "tenant_id", "sender_org_id", "created_at", "id"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_plain: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ANNOUNCEMENT",
        comment="ANNOUNCEMENT/BUSINESS/REMINDER/EMERGENCY")
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NORMAL",
        comment="NORMAL/IMPORTANT/EMERGENCY")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DRAFT",
        comment="DRAFT/PENDING_REVIEW/RETURNED/REJECTED/APPROVED/"
                "SCHEDULED/PUBLISHING/PUBLISHED/PARTIAL_FAILED/WITHDRAWN/EXPIRED")
    source_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="HUMAN",
        comment="HUMAN/BUSINESS_EVENT/PLATFORM")
    source_module: Mapped[str | None] = mapped_column(String(50))
    source_biz_type: Mapped[str | None] = mapped_column(String(50))
    source_biz_id: Mapped[int | None] = mapped_column(BigInteger)
    content_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SHARED",
        comment="SHARED/PER_RECIPIENT")
    template_id: Mapped[int | None] = mapped_column(BigInteger)
    template_version: Mapped[str | None] = mapped_column(String(30))
    sender_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    sender_context_id: Mapped[str | None] = mapped_column(String(64))
    sender_org_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_name_snapshot: Mapped[str | None] = mapped_column(String(100))
    sender_role_snapshot: Mapped[str | None] = mapped_column(String(64))
    org_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    publish_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="IMMEDIATE",
        comment="IMMEDIATE/SCHEDULED")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime)
    require_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    emergency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_key: Mapped[str | None] = mapped_column(String(80))
    action_params_json: Mapped[dict | None] = mapped_column(JSON)
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ack_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    audience_fingerprint: Mapped[str | None] = mapped_column(String(80))
    supersedes_campaign_id: Mapped[int | None] = mapped_column(BigInteger)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdrawn_by: Mapped[int | None] = mapped_column(BigInteger)
    withdraw_reason: Mapped[str | None] = mapped_column(String(500))
    channels_json: Mapped[list | None] = mapped_column(JSON)
    remark: Mapped[str | None] = mapped_column(String(500))
    ack_deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivery_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ASYNC", server_default="ASYNC",
        comment="SYNC/ASYNC")


class MessageDeliveryJob(PKMixin, TenantMixin, CommonMixin, Base):
    """t_message_delivery_job 万人级分批投递作业（租约领取）。"""
    __tablename__ = "t_message_delivery_job"
    __table_args__ = (
        Index("ix_msg_delivery_job_status_retry", "status", "next_retry_at", "id"),
        UniqueConstraint("tenant_id", "campaign_id", "cursor_start",
                         name="uk_msg_delivery_job_campaign_cursor"),
    )

    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    cursor_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="PENDING/PROCESSING/SUCCEEDED/RETRY_WAIT/DEAD")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by: Mapped[str | None] = mapped_column(String(80))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    recipient_slice_json: Mapped[list | None] = mapped_column(JSON)
    written_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500), comment="worker notes")


class MessageAudience(PKMixin, TenantMixin, CommonMixin, Base):
    """t_message_audience 受众规则（提交审核时快照；发布前再校验）。"""
    __tablename__ = "t_message_audience"
    __table_args__ = (
        Index("ix_audience_campaign", "tenant_id", "campaign_id", "id"),
    )

    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    audience_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="ALL_STUDENT/ALL_STAFF/ALL_USERS/COLLEGE/MAJOR/GRADE/"
                "ADMIN_CLASS/TEACHING_CLASS/ROLE/PERSON")
    include_or_exclude: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INCLUDE", comment="INCLUDE/EXCLUDE")
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    target_code: Mapped[str | None] = mapped_column(String(64))
    include_children: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rule_json: Mapped[dict | None] = mapped_column(JSON)
    rule_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1")
    resolved_count: Mapped[int | None] = mapped_column(Integer)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class MessageAttachment(PKMixin, TenantMixin, CommonMixin, Base):
    """t_message_attachment 发布单附件（只存文件中心 ID）。"""
    __tablename__ = "t_message_attachment"
    __table_args__ = (
        Index("ix_msg_attach_campaign", "tenant_id", "campaign_id", "sort_no"),
    )

    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_name_snapshot: Mapped[str | None] = mapped_column(String(200))


class MessageEventOutbox(PKMixin, TenantMixin, CommonMixin, Base):
    """t_message_event_outbox 业务事件 → 消息投递队列。"""
    __tablename__ = "t_message_event_outbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedup_key", name="uk_outbox_tenant_dedup"),
        Index("ix_outbox_status_retry", "status", "next_retry_at", "id"),
    )

    event_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_module: Mapped[str] = mapped_column(String(50), nullable=False)
    source_biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    recipient_refs_json: Mapped[list | None] = mapped_column(JSON)
    dedup_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="PENDING/PROCESSING/SUCCEEDED/RETRY_WAIT/DEAD")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    locked_by: Mapped[str | None] = mapped_column(String(80))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    campaign_id: Mapped[int | None] = mapped_column(BigInteger)
