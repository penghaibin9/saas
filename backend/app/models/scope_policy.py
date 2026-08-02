"""SYS-08 组织安全树：显式 DENY、精细 ALLOW 与未来生效。

与现有数据范围的关系
────────────────────
``t_data_scope_rule`` 已经提供了"角色 → 范围类型（SELF/CLASS/COLLEGE/MAJOR/SCHOOL/CUSTOM）"，
``data_scope_service`` 里也已有一套 provider（``_provider_college`` / ``_provider_counselor_classes``
等）真实参与鉴权。**缺的是显式 DENY**：今天只能表达"能看哪些"，无法表达"这个节点谁都不许看"。

本模块新增 ``t_scope_policy_target`` 与既有规则并存：既有规则继续提供基础范围，新表提供
显式 DENY、精细 ALLOW 和未来生效。判定顺序固定为

    DENY > 敏感专项 > 业务关系 > 直接 ALLOW > 继承 ALLOW > 默认拒绝

DENY 永远最先命中且不可被任何 ALLOW 覆盖——把"心理咨询中心的数据谁都不许看"这种要求
表达成"少给一个 ALLOW"是不可靠的，只要有人给角色加了个更大的范围就会被击穿。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Index, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

EFFECT_ALLOW = "ALLOW"
EFFECT_DENY = "DENY"
EFFECTS = (EFFECT_ALLOW, EFFECT_DENY)

# 目标类型与既有组织实体对齐，不引入第四种组织存储
TARGET_COLLEGE = "COLLEGE"
TARGET_MAJOR = "MAJOR"
TARGET_CLASS = "CLASS"
TARGET_DOMAIN = "DOMAIN"  # 业务域，如 PSYCHOLOGY / FUNDING，用于敏感专项
TARGET_TYPES = (TARGET_COLLEGE, TARGET_MAJOR, TARGET_CLASS, TARGET_DOMAIN)

# 判定顺序：数字小的先命中。DENY 恒为最高优先级。
PRECEDENCE = {
    "DENY": 0,
    "SENSITIVE": 1,
    "BUSINESS_RELATION": 2,
    "DIRECT_ALLOW": 3,
    "INHERITED_ALLOW": 4,
    "DEFAULT_DENY": 5,
}


class ScopePolicyTarget(PKMixin, TenantMixin, CommonMixin, Base):
    """一条范围策略：某角色对某组织节点/业务域的 ALLOW 或 DENY。"""

    __tablename__ = "t_scope_policy_target"

    role_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    effect: Mapped[str] = mapped_column(String(8), nullable=False, default=EFFECT_ALLOW)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    include_children: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否沿组织树向下继承"
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE", index=True)
    reason: Mapped[str | None] = mapped_column(String(1000))
    sensitive_domain: Mapped[str | None] = mapped_column(
        String(64), comment="敏感专项标记，如 PSYCHOLOGY；命中时优先级仅次于 DENY"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "role_code", "effect", "target_type", "target_id", "effective_at",
            name="uk_scope_policy_target",
        ),
        Index("idx_scope_policy_role_effect", "tenant_id", "role_code", "effect", "status"),
        Index("idx_scope_policy_target", "tenant_id", "target_type", "target_id", "status"),
    )


class ScopePolicyDecisionLog(PKMixin, TenantMixin, CommonMixin, Base):
    """范围模拟记录：页面上的"影响模拟"必须与真实判定同源，这里留下可比对的痕迹。"""

    __tablename__ = "t_scope_policy_decision_log"

    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    detail_json: Mapped[dict | None] = mapped_column(JSON)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)

    __table_args__ = (
        Index("idx_scope_decision_role_time", "tenant_id", "role_code", "created_at"),
    )
