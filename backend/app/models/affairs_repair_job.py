"""学工异议/申诉补偿任务：带租约、退避和人工重投能力。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AffairsRepairJob(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_affairs_repair_job"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedup_key", name="uk_affairs_repair_tenant_dedup"),
        Index("idx_affairs_repair_runnable", "tenant_id", "state", "next_run_at"),
        Index("idx_affairs_repair_lease", "tenant_id", "state", "lease_until"),
    )

    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)
    todo_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(500))
    payload_json: Mapped[dict | None] = mapped_column(JSON)
