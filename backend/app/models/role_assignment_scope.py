"""角色成员的五级组织/学生授权范围。

一行表示一条 ``t_user_role`` 关系被授予的一个范围节点。角色回答“能做什么”，
本表回答“以这个角色能管到哪里”。范围只保存稳定主键；名称仅作授权时审计快照。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class RoleAssignmentScope(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_role_assignment_scope"

    user_role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="SCHOOL/COLLEGE/MAJOR/CLASS/STUDENT"
    )
    scope_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="SCHOOL 固定 0；其余为对应主档稳定主键"
    )
    scope_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    granted_by: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_role_id", "scope_type", "scope_id",
            name="uk_role_assignment_scope_node",
        ),
        Index(
            "idx_role_assignment_scope_user_role",
            "tenant_id", "user_id", "role_code", "status",
        ),
        Index(
            "idx_role_assignment_scope_resource",
            "tenant_id", "scope_type", "scope_id", "status",
        ),
    )
