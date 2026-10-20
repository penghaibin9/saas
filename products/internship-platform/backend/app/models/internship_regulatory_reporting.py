"""Yiyang C07/G18 regulatory reporting facts."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipRegulatoryTemplateVersion(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_regulatory_template_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "report_code", "version_no", name="uk_ix_reg_tpl_version"),
        Index("ix_ix_reg_tpl_active", "tenant_id", "report_code", "status", "is_deleted"),
        Index("ix_ix_reg_tpl_source_file", "tenant_id", "source_file_id", "is_deleted"),
    )

    report_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="RP01/RP02")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_label: Mapped[str] = mapped_column(String(120), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    source_file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255))
    source_file_sha256: Mapped[str | None] = mapped_column(String(64))
    official_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="仅真实目标平台模板经正式联调确认后方可为1；采购基线必须为0",
    )
    field_schema_json: Mapped[list] = mapped_column(JSON, nullable=False)
    enum_schema_json: Mapped[dict | None] = mapped_column(JSON)
    cross_rule_json: Mapped[list | None] = mapped_column(JSON)
    mapping_schema_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", comment="ACTIVE/RETIRED")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    change_reason: Mapped[str | None] = mapped_column(String(500))


class InternshipRegulatoryTask(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_regulatory_task"
    __table_args__ = (
        UniqueConstraint("tenant_id", "task_no", name="uk_ix_reg_task_no"),
        Index("ix_ix_reg_task_batch", "tenant_id", "batch_id", "report_code", "status", "is_deleted"),
        Index("ix_ix_reg_task_output_file", "tenant_id", "output_file_id"),
        Index("ix_ix_reg_task_error_file", "tenant_id", "error_file_id"),
    )

    task_no: Mapped[str] = mapped_column(String(80), nullable=False)
    report_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    template_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="GENERATED",
        comment="GENERATED/VALIDATED/EXPORTED/SUBMITTED_EXTERNAL/RECEIPT_PENDING/ACCEPTED/REJECTED",
    )
    status_history_json: Mapped[list | None] = mapped_column(JSON)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_filename: Mapped[str | None] = mapped_column(String(255))
    output_file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    output_sha256: Mapped[str | None] = mapped_column(String(64))
    output_size: Mapped[int | None] = mapped_column(BigInteger)
    error_filename: Mapped[str | None] = mapped_column(String(255))
    error_file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    error_sha256: Mapped[str | None] = mapped_column(String(64))
    external_submission_ref: Mapped[str | None] = mapped_column(String(200))
    receipt_code: Mapped[str | None] = mapped_column(String(120))
    receipt_message: Mapped[str | None] = mapped_column(String(1000))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    receipt_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipRegulatoryTaskRow(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_regulatory_task_row"
    __table_args__ = (
        UniqueConstraint("tenant_id", "task_id", "row_no", name="uk_ix_reg_task_row_no"),
        Index("ix_ix_reg_task_row_valid", "tenant_id", "task_id", "is_valid", "is_deleted"),
    )

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    internship_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_errors_json: Mapped[list | None] = mapped_column(JSON)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
