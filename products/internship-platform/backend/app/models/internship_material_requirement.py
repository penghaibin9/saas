"""Configurable internship material collection requirements (Yiyang C03 / G09)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipMaterialRequirement(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_material_requirement"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", "material_code", name="uk_ix_material_requirement_code"),
        Index("ix_ix_material_requirement_status", "tenant_id", "batch_id", "status", "is_deleted"),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    material_code: Mapped[str] = mapped_column(String(80), nullable=False)
    material_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    audience_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ALL",
        comment="ALL/SELECTED_STUDENTS/FILTERED",
    )
    audience_filter_json: Mapped[dict | None] = mapped_column(
        JSON, comment="studentIds/collegeIds/classIds/majorIds 等正式范围条件"
    )
    allowed_extensions_json: Mapped[list | None] = mapped_column(JSON)
    min_files: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_files: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewer_permission: Mapped[str] = mapped_column(
        String(120), nullable=False, default="internship.material.review"
    )
    archive_category: Mapped[str] = mapped_column(
        String(80), nullable=False, default="CUSTOM_MATERIAL"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT",
        comment="DRAFT/PUBLISHED/CLOSED",
    )
    current_template_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)


class InternshipMaterialTemplateVersion(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_material_template_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "requirement_id", "version_no", name="uk_ix_material_template_version"),
        Index("ix_ix_material_template_current", "tenant_id", "requirement_id", "is_current", "is_deleted"),
    )

    requirement_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_name_snapshot: Mapped[str | None] = mapped_column(String(300))
    sha256_snapshot: Mapped[str | None] = mapped_column(String(64))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE",
        comment="ACTIVE/SUPERSEDED/REVOKED",
    )
    uploaded_by_name: Mapped[str | None] = mapped_column(String(100))


class InternshipMaterialSubmission(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_material_submission"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "requirement_id", "internship_id",
            name="uk_ix_material_submission_student_requirement",
        ),
        Index("ix_ix_material_submission_status", "tenant_id", "batch_id", "status", "is_deleted"),
    )

    requirement_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT",
        comment="DRAFT/SUBMITTED/APPROVED/RETURNED/WITHDRAWN",
    )
    submit_comment: Mapped[str | None] = mapped_column(String(500))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipMaterialSubmissionFile(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_material_submission_file"
    __table_args__ = (
        UniqueConstraint("tenant_id", "submission_id", "slot_no", name="uk_ix_material_submission_slot"),
        Index("ix_ix_material_submission_file_current", "tenant_id", "submission_id", "is_deleted"),
    )

    submission_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    slot_no: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    current_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
