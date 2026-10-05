"""培养方案版本承接记录；原执行任务和原业务历史保持原样。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utc_now_naive
from app.models.base import AuditTimeMixin, Base, PKMixin, TenantMixin


class AaTeachingTaskSourceHandoff(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_aa_teaching_task_source_handoff"

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    execution_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    successor_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    execution_source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    successor_source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    confirmed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "successor_task_id", name="uk_aa_task_handoff_successor"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_aa_task_handoff_idem"),
        CheckConstraint("execution_task_id <> successor_task_id", name="ck_aa_task_handoff_distinct"),
        Index("ix_aa_task_handoff_execution", "tenant_id", "term_id", "execution_task_id"),
    )
