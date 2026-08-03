"""SYS-10 访问解释、权限复核、职责分离与紧急访问。

解释器为什么不能自己算
──────────────────────
``app.core.permissions.has_permission`` 只返回 True/False，不给原因。很容易想到的做法是
在解释器里"照着它的逻辑再写一遍"，把每一步打印出来——**这是错的**。两套逻辑必然随时间
漂移，等它们不一致时，解释会理直气壮地告诉管理员一个与实际相反的结论，比没有解释更糟。

正确做法：解释器只调用真实函数（``is_super_admin`` / ``get_effective_permission_patterns``
/ ``has_permission`` / ``scope_policy_service.decide``），把中间量展开成可读的链路，
**最终结论一律以 has_permission 为准**；若链路推导与它不一致，标记 ``EXPLAINER_DRIFT``
并如实报出来，而不是二选一。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, DateTime, Index, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (AuditTimeMixin, Base, CommonMixin, PKMixin,
                             TenantMixin)

DECISION_ALLOW = "ALLOW"
DECISION_DENY = "DENY"

# 复核活动状态
REVIEW_DRAFT = "DRAFT"
REVIEW_RUNNING = "RUNNING"
REVIEW_CLOSED = "CLOSED"

# 复核结论：不允许只打勾不处理
REVIEW_KEEP = "KEEP"
REVIEW_ADJUST = "ADJUST"
REVIEW_REVOKE = "REVOKE"
REVIEW_EXCEPTION = "EXCEPTION"
REVIEW_DECISIONS = (REVIEW_KEEP, REVIEW_ADJUST, REVIEW_REVOKE, REVIEW_EXCEPTION)


class AccessDecisionTrace(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """决策留痕（append-only）。真实 403 返回 traceId，事后可按它复现当时的判定链。

    ``resource_id_hash`` 存哈希而非原值：解释接口不该成为"某个对象是否存在"的探测器。
    """

    __tablename__ = "t_access_decision_trace"

    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_user_id: Mapped[int | None] = mapped_column(BigInteger)
    active_role_code: Mapped[str | None] = mapped_column(String(64))
    action_code: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id_hash: Mapped[str | None] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    security_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="逐层 PASS/FAIL 链")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="留痕保留期，到期由清理任务处理")

    __table_args__ = (
        UniqueConstraint("tenant_id", "trace_id", name="uk_access_trace"),
        Index("idx_access_subject_time", "tenant_id", "subject_user_id", "created_at"),
        Index("idx_access_decision_reason", "tenant_id", "decision", "reason_code", "created_at"),
    )


class AccessReviewCampaign(PKMixin, TenantMixin, CommonMixin, Base):
    """一轮权限复核。高权角色按季度、普通角色按半年。"""

    __tablename__ = "t_access_review_campaign"

    campaign_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    scope_json: Mapped[dict | None] = mapped_column(JSON, comment="本轮覆盖哪些角色")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=REVIEW_DRAFT, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("tenant_id", "campaign_code", name="uk_review_campaign_code"),
        Index("idx_review_campaign_status", "tenant_id", "status", "due_at"),
    )


class AccessReviewItem(PKMixin, TenantMixin, CommonMixin, Base):
    """复核明细。结论只能是保留/调整/回收/例外——不允许"打个勾就算复核过"。"""

    __tablename__ = "t_access_review_item"

    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    subject_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(24), comment="KEEP/ADJUST/REVOKE/EXCEPTION")
    decided_by: Mapped[int | None] = mapped_column(BigInteger)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(String(1000))
    follow_up_change_set_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="回收/调整必须落到一次安全变更，避免只在复核表里写个结论就完事"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "campaign_id", "subject_user_id", "role_code", name="uk_review_item"),
        Index("idx_review_item_pending", "tenant_id", "campaign_id", "decision"),
    )


class SodRule(PKMixin, TenantMixin, CommonMixin, Base):
    """职责分离规则：同一个人不得同时持有这两个角色。"""

    __tablename__ = "t_sod_rule"

    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    role_a: Mapped[str] = mapped_column(String(64), nullable=False)
    role_b: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="HIGH")
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE", index=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_code", name="uk_sod_rule_code"),
        Index("idx_sod_rule_roles", "tenant_id", "role_a", "role_b", "status"),
    )


class SodViolation(PKMixin, TenantMixin, CommonMixin, Base):
    """检出的职责冲突。检出不等于放行——后端必须真的拦住。"""

    __tablename__ = "t_sod_violation"

    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    detected_roles_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN", index=True)
    resolution: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_code", "subject_user_id", name="uk_sod_violation"),
        Index("idx_sod_violation_status", "tenant_id", "status"),
    )


class EmergencyAccessSession(PKMixin, TenantMixin, CommonMixin, Base):
    """紧急访问（break-glass）。必须短时、有事由、可审计，且默认无人长期持有。"""

    __tablename__ = "t_emergency_access_session"

    session_code: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    granted_role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_ref: Mapped[str] = mapped_column(String(200), nullable=False, comment="工单或事件号，不允许空口开通")
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="必填：不存在无限期紧急访问")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE", index=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "session_code", name="uk_emergency_session_code"),
        Index("idx_emergency_active", "tenant_id", "subject_user_id", "status", "expires_at"),
    )
