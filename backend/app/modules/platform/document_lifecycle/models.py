"""PLAT-C private ORM declarations.

Do not import this module from ``app.models`` or ``app.db.base`` until PLAT-C receives the
third A -> B -> C migration/registration slot.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class FileDerivedArtifact(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_derived_artifact"

    source_file_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    derivative_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    extractor_code: Mapped[str] = mapped_column(String(80), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_file_object_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    block_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    sensitivity_level: Mapped[str] = mapped_column(String(30), nullable=False)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_file_version_id", "source_sha256", "derivative_kind",
            "extractor_code", "extractor_version", name="uk_file_derived_artifact_identity",
        ),
        Index("ix_file_derived_source", "tenant_id", "source_file_version_id", "status", "id"),
    )


class DocumentCompareResult(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_document_compare_result"

    left_file_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    left_source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    right_file_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    right_source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_code: Mapped[str] = mapped_column(String(80), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_file_object_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    diff_sha256: Mapped[str | None] = mapped_column(String(64))
    summary_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    sensitivity_level: Mapped[str] = mapped_column(String(30), nullable=False)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "left_file_version_id", "left_source_sha256",
            "right_file_version_id", "right_source_sha256", "algorithm_code",
            "algorithm_version", name="uk_document_compare_identity",
        ),
        Index("ix_document_compare_left", "tenant_id", "left_file_version_id", "status", "id"),
        Index("ix_document_compare_right", "tenant_id", "right_file_version_id", "status", "id"),
    )


class StudentLifecycleFact(PKMixin, TenantMixin, Base):
    """Append-only cross-domain milestone projection; never a business-state authority."""

    __tablename__ = "t_student_lifecycle_fact"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    source_module: Mapped[str] = mapped_column(String(64), nullable=False)
    fact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_biz_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_biz_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_version: Mapped[str] = mapped_column(String(100), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    importance: Mapped[str] = mapped_column(String(30), nullable=False, default="NORMAL")
    visibility_code: Mapped[str] = mapped_column(String(50), nullable=False)
    sensitivity_level: Mapped[str] = mapped_column(String(30), nullable=False)
    target_ref_json: Mapped[dict | None] = mapped_column(JSON)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uk_student_lifecycle_fact_dedupe"),
        Index("ix_lifecycle_fact_timeline", "tenant_id", "student_id", "event_time", "id"),
        Index("ix_lifecycle_fact_module", "tenant_id", "student_id", "source_module", "event_time", "id"),
    )
