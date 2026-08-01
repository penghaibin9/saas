"""文件存储配额预留账本。

配额判断与物理写入之间必须由持久化 HELD 记录占住容量；成功登记 FileObject 后消费，
失败、放弃或过期时释放，避免并发请求同时通过容量检查。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class FileStorageQuotaReservation(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_file_storage_quota_reservation"

    reservation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    module_code: Mapped[str] = mapped_column(String(64), nullable=False, default="SHARED")
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str] = mapped_column(String(500), nullable=False)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="HELD")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_file_id: Mapped[int | None] = mapped_column(BigInteger)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    release_reason: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        UniqueConstraint("tenant_id", "reservation_key", name="uk_file_quota_reservation_key"),
        Index(
            "ix_file_quota_reservation_active",
            "tenant_id", "status", "expires_at", "id",
        ),
        Index(
            "ix_file_quota_reservation_source",
            "tenant_id", "source_type", "source_id",
        ),
    )
