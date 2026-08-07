"""包 11：处分追加式决定版本与唯一活动子流程锁。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TenantMixin


class DisciplineDecisionVersion(PKMixin, TenantMixin, Base):
    """处分决定追加式版本；数据库触发器禁止 UPDATE/DELETE。"""

    __tablename__ = "t_affairs_discipline_decision_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "case_id", "version_no",
                         name="uk_disc_decision_case_ver"),
    )

    case_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    disc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    doc_no: Mapped[str | None] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decided_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class DisciplineSubflowLock(PKMixin, TenantMixin, Base):
    """同一处分主案只能存在一个活动申诉或解除流程。"""

    __tablename__ = "t_affairs_discipline_subflow_lock"
    __table_args__ = (
        UniqueConstraint("tenant_id", "case_id", name="uk_disc_active_subflow"),
        UniqueConstraint("tenant_id", "flow_type", "flow_id",
                         name="uk_disc_subflow_source"),
    )

    case_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    flow_type: Mapped[str] = mapped_column(String(20), nullable=False)
    flow_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
