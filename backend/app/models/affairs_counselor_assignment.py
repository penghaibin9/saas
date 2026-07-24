"""班级—辅导员真实责任关系（主责/协同/临时代班及历史）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AffairsCounselorAssignment(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_affairs_counselor_assignment"
    __table_args__ = (
        Index("ix_affairs_counselor_assignment_class_status", "tenant_id", "class_id", "status"),
        Index("ix_affairs_counselor_assignment_user_status", "tenant_id", "user_id", "status"),
    )

    class_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="行政班 t_class.id")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="辅导员 t_user.id")
    duty_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="PRIMARY/CO/TEMP")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", comment="ACTIVE/ENDED")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500))
    handover_from_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    version: Mapped[int] = mapped_column(default=1, nullable=False, comment="乐观锁")
