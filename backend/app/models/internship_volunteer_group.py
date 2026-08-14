"""Volunteer-group coordination fact for canonical InternshipApplication slots 1/2/3.

This model never stores position choices. Those remain on InternshipApplication.volunteer_no
1/2/3. The group only coordinates submission version, immutable material, enterprise lock and
school confirmation lifecycle.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipVolunteerGroup(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_volunteer_group"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "record_id", "campaign_id",
            name="uk_intern_volunteer_group_record_campaign",
        ),
        Index(
            "ix_intern_volunteer_group_student_status",
            "tenant_id", "student_id", "campaign_id", "status", "is_deleted",
        ),
        Index(
            "ix_intern_volunteer_group_campaign_deadline",
            "tenant_id", "campaign_id", "status", "teacher_confirm_deadline", "is_deleted",
        ),
        Index(
            "ix_intern_volunteer_group_record_status",
            "tenant_id", "record_id", "status", "is_deleted",
        ),
    )

    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_record.id")
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_student_profile.id")
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_batch.id")
    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_recruitment_campaign.id")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DRAFT",
        comment="DRAFT/SUBMITTED/LOCKED/NEEDS_REVISION/APPROVED",
    )
    submission_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_material_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="→ t_internship_application_material_snapshot.id"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by_decision_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="最近触发 LOCKED 的 EnterpriseApplicationDecision；历史 Decision 不删除"
    )
    teacher_confirm_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    revision_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    revision_reason: Mapped[str | None] = mapped_column(String(500))
    last_released_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_release_reason: Mapped[str | None] = mapped_column(String(500))
    released_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    contact_consent_revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
