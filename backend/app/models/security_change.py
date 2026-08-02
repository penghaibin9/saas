"""SYS-09 安全变更：草稿、审核、排期、激活与回滚。

先讲清楚这张卡实际管什么
────────────────────────
事实冻结的结论是：``app.core.permissions`` 里**没有任何缓存**，权限判定是对代码常量
``ROLE_PERMISSIONS`` 的纯查表；系统里也**不存在权限版本号**。这去掉了本卡最容易出事的
一环——不需要处理多实例缓存失效。

因此"安全变更"真正能改变的，是数据库里那部分**可变的权限配置**：

- ``t_custom_role_source``：学校自定义角色的权限清单（SYS-06）
- ``t_scope_policy_target``：数据范围的 ALLOW / DENY（SYS-08）

本卡把对它们的修改收进"变更集"：草稿、审核、排期期间**一个字节都不写目标表**，
只有激活那一刻才在单事务内应用并生成新的 securityRevision。这样"草稿不改变真实权限"
不是靠代码自觉，而是物理上没写。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, DateTime, Index, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

# 状态机（V6 SYS-09 固定顺序）
CHANGE_DRAFT = "DRAFT"
CHANGE_PENDING_REVIEW = "PENDING_REVIEW"
CHANGE_APPROVED = "APPROVED"
CHANGE_SCHEDULED = "SCHEDULED"
CHANGE_ACTIVATED = "ACTIVATED"
CHANGE_REJECTED = "REJECTED"
CHANGE_ROLLED_BACK = "ROLLED_BACK"

CHANGE_STATUSES = (
    CHANGE_DRAFT,
    CHANGE_PENDING_REVIEW,
    CHANGE_APPROVED,
    CHANGE_SCHEDULED,
    CHANGE_ACTIVATED,
    CHANGE_REJECTED,
    CHANGE_ROLLED_BACK,
)

# 变更目标：只允许这两种，且都必须有对应的 apply/revert 实现。
# 不做成"任意表任意字段"的通用改写器——那等于给了一把能改任何东西的钥匙。
TARGET_CUSTOM_ROLE = "CUSTOM_ROLE"
TARGET_SCOPE_POLICY = "SCOPE_POLICY"
TARGET_TYPES = (TARGET_CUSTOM_ROLE, TARGET_SCOPE_POLICY)

RISK_NORMAL = "NORMAL"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"


class SecurityChangeSet(PKMixin, TenantMixin, CommonMixin, Base):
    """一次安全变更。审核与激活分离，一人阶段用加强型自复核补位。"""

    __tablename__ = "t_security_change_set"

    change_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=CHANGE_DRAFT, index=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default=RISK_NORMAL)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    impact_json: Mapped[dict | None] = mapped_column(JSON, comment="提交审核时算出的影响面快照")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_user: Mapped[int | None] = mapped_column(BigInteger, comment="发起人")
    reviewed_by_user: Mapped[int | None] = mapped_column(BigInteger, comment="复核人")
    activated_by_user: Mapped[int | None] = mapped_column(BigInteger, comment="激活人")
    review_note: Mapped[str | None] = mapped_column(String(1000))
    self_review_ack: Mapped[str | None] = mapped_column(
        String(200), comment="一人阶段自复核确认文本，必须逐字输入，防误点"
    )
    activated_revision: Mapped[int | None] = mapped_column(Integer, comment="激活后产生的 securityRevision")

    __table_args__ = (
        UniqueConstraint("tenant_id", "change_code", name="uk_security_change_code"),
        Index("idx_security_change_status_schedule", "tenant_id", "status", "scheduled_at"),
    )


class SecurityChangeItem(PKMixin, TenantMixin, CommonMixin, Base):
    """变更集里的一条具体改动。``before_json`` 在激活时写入，供回滚使用。"""

    __tablename__ = "t_security_change_item"

    change_set_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="角色码或策略 id")
    before_json: Mapped[dict | None] = mapped_column(JSON, comment="激活时抓取的原值快照")
    after_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="要改成什么")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_security_item_set", "tenant_id", "change_set_id"),
        Index("idx_security_item_target", "tenant_id", "target_type", "target_id"),
    )


class SecurityActivation(PKMixin, TenantMixin, CommonMixin, Base):
    """激活流水：每成功激活或回滚一次，产生一个新的 securityRevision。

    ``(tenant_id, revision)`` 唯一——并发激活时数据库兜底，只有一个能拿到下一个号，
    不依赖应用层先查后写。
    """

    __tablename__ = "t_security_activation"

    revision: Mapped[int] = mapped_column(Integer, nullable=False, comment="租户内递增的安全版本号")
    change_set_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(24), nullable=False, comment="ACTIVATE / ROLLBACK")
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="本次实际应用的全部改动")
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "revision", name="uk_security_revision"),
        Index("idx_security_activation_time", "tenant_id", "created_at"),
    )
