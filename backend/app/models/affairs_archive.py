"""13A-P6 学工归档模型（草案 §3.9）。

归档批次 + 学生档案包（每生一行,缺项清单）。水印包走 export 管线落 t_export_task(不建归档文件表)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
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
    """学生档案包（批次内每生一行,缺项清单）。包文件走 t_file_object,导出留痕 t_export_task。"""
    __tablename__ = "t_affairs_archive_package"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    missing_items_json: Mapped[str | None] = mapped_column(String(2000), comment="缺项清单")
    package_file_id: Mapped[int | None] = mapped_column(BigInteger, comment="→ t_file_object")
    export_task_id: Mapped[int | None] = mapped_column(BigInteger, comment="→ t_export_task")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_GEN", index=True,
                                        comment="PENDING_GEN/PENDING_SUPPLEMENT/SUBMITTED/ARCHIVED/RETURNED")
