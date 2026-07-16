"""真实演示沙箱的基线记录索引。"""
from __future__ import annotations

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, PKMixin, TenantMixin


class SandboxBaseline(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """标记由系统预制、普通业务操作不得删除的演示记录。"""

    __tablename__ = "t_sandbox_baseline"
    __table_args__ = (
        UniqueConstraint("tenant_id", "table_name", "row_id", name="uk_sandbox_baseline_row"),
    )

    table_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    row_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(200))
