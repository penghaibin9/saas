"""Durable technical effect of a committed grade publication; no copied grade facts."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AcademicGradeEffectJob(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = 't_aa_grade_effect_job'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'source_kind', 'source_id', name='uk_aa_grade_effect_source'),
        Index('ix_aa_grade_effect_due', 'tenant_id', 'state', 'next_run_at'),
    )
    grade_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default='PENDING')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(200))
    result_json: Mapped[dict | None] = mapped_column(JSON)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
