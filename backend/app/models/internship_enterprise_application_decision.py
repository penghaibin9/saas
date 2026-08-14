"""Enterprise application decision side fact; never a placement result."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipEnterpriseApplicationDecision(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_enterprise_application_decision"
    __table_args__ = (
        UniqueConstraint("tenant_id", "application_id", "material_snapshot_id", name="uk_intern_enterprise_decision_app_snapshot"),
        Index("ix_intern_enterprise_decision_company_campaign_status", "tenant_id", "company_id", "campaign_id", "decision_status", "is_deleted"),
        Index("ix_intern_enterprise_decision_application", "tenant_id", "application_id", "is_deleted"),
    )

    application_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    volunteer_group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    position_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    material_snapshot_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submission_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", comment="PENDING/INTERESTED/INTERVIEW/ACCEPT_INTENT/REJECTED")
    interview_at: Mapped[datetime | None] = mapped_column(DateTime)
    interview_note: Mapped[str | None] = mapped_column(String(1000))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
    decided_by_member_id: Mapped[int | None] = mapped_column(BigInteger)
    decided_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
