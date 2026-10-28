"""公共文件对象、扫描、资产版本、绑定、归档与存储治理模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class FileObject(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_object"

    file_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="兼容存储 key")
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
    bucket_name: Mapped[str | None] = mapped_column(String(150))
    object_key: Mapped[str | None] = mapped_column(String(500))
    etag: Mapped[str | None] = mapped_column(String(128))
    legacy_file_key: Mapped[str | None] = mapped_column(String(500))
    storage_migrated_at: Mapped[datetime | None] = mapped_column(DateTime)
    storage_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
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
        Index("ix_file_storage_object", "storage_backend", "bucket_name", "object_key"),
        Index("ix_file_storage_migration", "tenant_id", "storage_backend", "storage_migrated_at", "id"),
        Index("ix_file_retention_cleanup", "tenant_id", "legal_hold", "is_deleted", "retention_until", "id"),
    )


class FileAsset(PKMixin, TenantMixin, CommonMixin, Base):
    """逻辑文件资产。物理字节不可覆盖，重交通过 FileVersion 递增。"""
    __tablename__ = "t_file_asset"

    asset_code: Mapped[str] = mapped_column(String(180), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(30), nullable=False, default="BUSINESS_OBJECT")
    owner_id: Mapped[str | None] = mapped_column(String(64), index=True)
    current_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", comment="ACTIVE/LOCKED/ARCHIVED/DELETED")
    version_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sensitivity_level: Mapped[str] = mapped_column(String(30), nullable=False, default="PERSONAL")

    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_code", name="uk_file_asset_code"),
        Index("ix_file_asset_owner", "tenant_id", "owner_type", "owner_id"),
        Index("ix_file_asset_category", "tenant_id", "category_code", "lifecycle_status"),
    )


class FileVersion(PKMixin, TenantMixin, CommonMixin, Base):
    """逻辑资产版本；每一版只指向一个不可变 FileObject。"""
    __tablename__ = "t_file_version"

    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_channel: Mapped[str] = mapped_column(String(40), nullable=False, default="LEGACY_ADAPTER")
    uploader_user_id: Mapped[str | None] = mapped_column(String(64))
    uploader_name_snapshot: Mapped[str | None] = mapped_column(String(100))
    submit_comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="UPLOADED", comment="UPLOADED/SCANNING/READY/SUBMITTED/APPROVED/REJECTED/INVALIDATED/ARCHIVED")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime)
    invalidated_by: Mapped[str | None] = mapped_column(String(100))
    invalid_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_id", "version_no", name="uk_file_version_no"),
        UniqueConstraint("tenant_id", "asset_id", "file_object_id", name="uk_file_version_object"),
        Index("ix_file_version_current", "tenant_id", "asset_id", "is_current", "status"),
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


class FileBinding(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_binding"
    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[str] = mapped_column(String(64), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(40), nullable=False, default="ATTACHMENT")
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False, default="BUSINESS_OBJECT")
    subject_id: Mapped[str | None] = mapped_column(String(64))
    batch_id: Mapped[str | None] = mapped_column(String(64))
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    scope_json: Mapped[dict | None] = mapped_column(JSON)
    asset_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    module_code: Mapped[str | None] = mapped_column(String(64), index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    data_scope_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (
        UniqueConstraint("tenant_id", "file_id", "biz_type", "biz_id", "relation_type", name="uk_file_binding_relation"),
        UniqueConstraint("tenant_id", "version_id", "module_code", "biz_type", "biz_id", "relation_type", name="uk_file_binding_version_relation"),
        Index("ix_file_binding_business", "tenant_id", "biz_type", "biz_id", "is_current"),
        Index("ix_file_binding_subject", "tenant_id", "subject_type", "subject_id"),
        Index("ix_file_binding_batch", "tenant_id", "batch_id"),
        Index("ix_file_binding_asset_current", "tenant_id", "asset_id", "version_id", "is_current"),
    )


class ArchiveManifest(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_archive_manifest"
    module_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    archive_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PREPARED", comment="PREPARED/FROZEN/PACKAGED/SUPERSEDED/REVOKED/ABORTED")
    rule_version: Mapped[str | None] = mapped_column(String(64))
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    package_file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by: Mapped[str | None] = mapped_column(String(100))
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_code", "archive_type", "target_type", "target_id", "revision", name="uk_archive_manifest_revision"),
        Index("ix_archive_manifest_target", "tenant_id", "module_code", "target_type", "target_id", "status"),
    )


class ArchiveManifestItem(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_archive_manifest_item"
    manifest_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    material_code: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_name_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    size_snapshot: Mapped[int | None] = mapped_column(BigInteger)
    sha256_snapshot: Mapped[str | None] = mapped_column(String(64))
    review_status: Mapped[str | None] = mapped_column(String(40))
    scan_result: Mapped[str] = mapped_column(String(30), nullable=False)
    uploader_snapshot: Mapped[str | None] = mapped_column(String(100))
    submitted_at_snapshot: Mapped[datetime | None] = mapped_column(DateTime)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    __table_args__ = (
        UniqueConstraint("tenant_id", "manifest_id", "version_id", "material_code", name="uk_archive_manifest_item_version"),
        Index("ix_archive_manifest_item_order", "tenant_id", "manifest_id", "sort_no", "id"),
    )


class FileRetentionPolicy(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_retention_policy"
    policy_code: Mapped[str] = mapped_column(String(100), nullable=False)
    module_code: Mapped[str | None] = mapped_column(String(64))
    biz_type: Mapped[str | None] = mapped_column(String(80))
    storage_zone: Mapped[str | None] = mapped_column(String(30))
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    cleanup_action: Mapped[str] = mapped_column(String(30), nullable=False, default="DELETE_BYTES")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_code", name="uk_file_retention_policy_code"),
        Index("ix_file_retention_policy_match", "tenant_id", "is_active", "module_code", "biz_type", "storage_zone", "priority"),
    )


class TenantStorageQuota(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_tenant_storage_quota"
    total_quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warning_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    hard_limit_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    module_quota_json: Mapped[dict | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uk_tenant_storage_quota"),
        Index("ix_tenant_storage_quota_enabled", "tenant_id", "hard_limit_enabled", "is_deleted"),
    )
