"""PLAT-05 客户健康、工单、培训与续费。

健康分不落表——由 go_live_check_service（SYS-01）、incident_service
（PLAT-09，按 t_incident_tenant 过滤到本校）、本卡自己的工单积压、
platform_service.tenant_meta 到期时间四类既有真实信号实时算出，落表反而
会变成一份随时可能与源头脱节的"第二份健康分"。这里只持久化真正需要状态
机和时间线的三类客户成功活动：工单、培训、续费任务。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class SupportTicket(PKMixin, TenantMixin, CommonMixin, Base):
    """t_support_ticket 客户成功工单。"""
    __tablename__ = "t_support_ticket"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="P2",
                                          comment="P0/P1/P2/P3")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", index=True,
        comment="OPEN/IN_PROGRESS/RESOLVED/CLOSED")
    reporter_name: Mapped[str | None] = mapped_column(String(100))
    assignee_user_id: Mapped[int | None] = mapped_column(BigInteger)
    assignee_name: Mapped[str | None] = mapped_column(String(100))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolution_note: Mapped[str | None] = mapped_column(String(2000))


class TrainingRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """t_training_record 客户培训记录。"""
    __tablename__ = "t_training_record"

    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    trainer_name: Mapped[str | None] = mapped_column(String(100))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SCHEDULED", index=True,
        comment="SCHEDULED/COMPLETED/CANCELLED")
    attendee_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(String(1000))


class RenewalTask(PKMixin, TenantMixin, CommonMixin, Base):
    """t_renewal_task 续费跟进任务。"""
    __tablename__ = "t_renewal_task"

    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", index=True,
        comment="PENDING/CONTACTED/COMMITTED/RENEWED/CHURNED")
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger)
    owner_name: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(String(1000))
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
