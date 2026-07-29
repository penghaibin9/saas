"""公共文件对象、扫描记录、上传会话与文件任务。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class FileObject(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_object"

    file_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="存储 key")
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    ext: Mapped[str | None] = mapped_column(String(20))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    biz_type: Mapped[str | None] = mapped_column(String(50))
    biz_id: Mapped[str | None] = mapped_column(String(64), index=True)
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="PRIVATE")
    security_level: Mapped[str] = mapped_column(String(30), nullable=False, default="NORMAL")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="AVAILABLE")
    remark: Mapped[str | None] = mapped_column(String(500))

    storage_backend: Mapped[str] = mapped_column(String(30), nullable=False, default="local")
    storage_zone: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    upload_source: Mapped[str] = mapped_column(String(30), nullable=False, default="USER")
    scan_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    scan_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_REQUIRED", index=True)
    scan_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scan_engine: Mapped[str | None] = mapped_column(String(50))
    scan_engine_version: Mapped[str | None] = mapped_column(String(120))
    scan_signature_version: Mapped[str | None] = mapped_column(String(120))
    scan_last_error: Mapped[str | None] = mapped_column(Text)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime)
    available_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_file_object_scan_queue", "tenant_id", "scan_required", "scan_status", "created_at"),
    )


class FileScanRecord(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_scan_record"

    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    engine: Mapped[str] = mapped_column(String(50), nullable=False, default="CLAMAV")
    engine_version: Mapped[str | None] = mapped_column(String(120))
    signature_version: Mapped[str | None] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    threat_name: Mapped[str | None] = mapped_column(String(300))
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    details_json: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("tenant_id", "file_id", "attempt", name="uk_file_scan_record_attempt"),
        Index("ix_file_scan_record_result", "tenant_id", "result", "created_at"),
    )


class FileUploadSession(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_upload_session"

    session_key: Mapped[str] = mapped_column(String(64), nullable=False)
    file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CREATED")
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="LEGACY_API")
    file_name: Mapped[str | None] = mapped_column(String(300))
    expected_size: Mapped[int | None] = mapped_column(BigInteger)
    received_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("tenant_id", "session_key", name="uk_file_upload_session_key"),
        Index("ix_file_upload_session_status", "tenant_id", "status", "created_at"),
    )


class FileJob(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_job"

    job_type: Mapped[str] = mapped_column(String(40), nullable=False, default="FILE_SCAN")
    file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by: Mapped[str | None] = mapped_column(String(120))
    last_error: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    result_json: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uk_file_job_dedupe"),
        Index("ix_file_job_claim", "job_type", "status", "available_at", "locked_at"),
    )
