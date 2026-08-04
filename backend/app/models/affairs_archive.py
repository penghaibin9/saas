"""学工归档批次、学生档案包与公共版本 Manifest。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class ArchiveBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """学工归档批次。DRAFT/COLLECTING/COLLEGE_REVIEW/SA_CONFIRM/ARCHIVED。"""
    __tablename__ = "t_affairs_archive_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    year_code: Mapped[str | None] = mapped_column(String(50), index=True)
    scope_json: Mapped[str | None] = mapped_column(String(2000))
    confirm_by: Mapped[str | None] = mapped_column(String(100))
    confirm_at: Mapped[datetime | None] = mapped_column(DateTime)
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)


class ArchivePackage(PKMixin, TenantMixin, CommonMixin, Base):
    """每生一份档案包；文件版本与清单均指向公共文件冻结中心。"""
    __tablename__ = "t_affairs_archive_package"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    missing_items_json: Mapped[str | None] = mapped_column(String(2000), comment="缺项清单")
    package_file_id: Mapped[int | None] = mapped_column(BigInteger, comment="兼容 → t_file_object")
    export_task_id: Mapped[int | None] = mapped_column(BigInteger, comment="兼容 → t_export_task")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING_GEN", index=True,
        comment="PENDING_GEN/GENERATING/PENDING_SUPPLEMENT/SUBMITTED/ARCHIVED/RETURNED",
    )

    generation_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_error: Mapped[str | None] = mapped_column(String(1000))
    generation_lease_token: Mapped[str | None] = mapped_column(String(64), index=True)
    generation_lease_until: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    package_asset_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    package_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    manifest_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    manifest_revision: Mapped[int | None] = mapped_column(Integer)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index(
            "ix_affairs_archive_package_manifest",
            "tenant_id", "batch_id", "student_id", "manifest_id",
        ),
    )
