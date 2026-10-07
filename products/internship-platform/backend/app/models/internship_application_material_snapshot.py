"""Immutable internship application material snapshots.

One submission snapshot is shared by volunteer 1/2/3. Per-position application statements stay
on each canonical InternshipApplication row and are never copied into this common snapshot.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, PKMixin, TenantMixin


class InternshipApplicationMaterialSnapshot(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_internship_application_material_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "volunteer_group_id", "submission_version",
            name="uk_intern_material_snapshot_submission",
        ),
        Index(
            "ix_intern_material_snapshot_group_version",
            "tenant_id", "volunteer_group_id", "submission_version",
        ),
        Index(
            "ix_intern_material_snapshot_student_created",
            "tenant_id", "student_id", "created_at",
        ),
        Index(
            "ix_intern_material_snapshot_campaign_student",
            "tenant_id", "campaign_id", "student_id",
        ),
    )

    volunteer_group_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_volunteer_group.id（M4）")
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_student_profile.id")
    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_recruitment_campaign.id")
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_batch.id")
    submission_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    school_fact_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    attachment_file_ids_json: Mapped[list | None] = mapped_column(JSON)
    material_policy_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    consent_version: Mapped[str] = mapped_column(String(80), nullable=False)
    consent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    contact_sharing_policy: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    generated_profile_pdf_file_id: Mapped[int | None] = mapped_column(BigInteger)
