"""SYS-07 角色成员的有效期扩展。

为什么是"扩展"而不是"改造 t_user_role"
──────────────────────────────────────
``t_user_role`` 是登录鉴权的必经之路（``auth_service_db._role_contexts`` 只认
``status == "ACTIVE"`` 的行）。给它加列、改语义，一旦出错全校登录一起挂。
所以有效期单独一张表，用 ``user_role_id`` 挂在原表旁边：

- 授权仍然写原表（学校现有一切读法都不用改）；
- 到期由本模块把原表那一行的 ``status`` 从 ACTIVE 翻成 EXPIRED——
  **鉴权侧一个字都不用改就立刻生效**，这就是"到期无需重新登录即失效"的落点；
- 谁授的、为什么、到什么时候、什么时候复核过，记在这张表上。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, DateTime, Index, String, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

VALIDITY_ACTIVE = "ACTIVE"
VALIDITY_EXPIRED = "EXPIRED"
VALIDITY_REVOKED = "REVOKED"

SOURCE_MANUAL = "MANUAL"                    # 管理员手工授予
SOURCE_IMPORT = "IMPORT"                    # 统一导入
SOURCE_IMPLEMENTATION = "IMPLEMENTATION"    # 实施预设安装
SOURCE_SECURITY_CHANGE = "SECURITY_CHANGE"  # 安全变更激活
SOURCE_TRANSFER = "TRANSFER"                # 工作转交
SOURCE_UNKNOWN = "UNKNOWN"                  # 历史数据回填不出来源


class RoleAssignmentValidity(PKMixin, TenantMixin, CommonMixin, Base):
    """一行 = 一条角色成员关系的有效期与来源。没有行 = 历史长期授权（来源不明）。"""

    __tablename__ = "t_role_assignment_validity"

    user_role_id: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                              comment="= t_user_role.id")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="空=长期有效")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default=SOURCE_MANUAL)
    source_id: Mapped[str | None] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(String(500))
    granted_by: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=VALIDITY_ACTIVE)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger)
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_reviewed_term: Mapped[str | None] = mapped_column(String(64), comment="最近一次复核所在学期")
    transferred_to_user_id: Mapped[int | None] = mapped_column(BigInteger, comment="转交去向")

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_role_id", name="uk_role_assignment_validity"),
        Index("idx_role_validity_expires", "tenant_id", "status", "expires_at"),
        Index("idx_role_validity_user_role", "tenant_id", "user_id", "role_code"),
    )
