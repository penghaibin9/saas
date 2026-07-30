"""统一导入导出任务中心模型。

阶段 3 采用 adapter 方式承接现有身份导入、老系统迁移和公共 Excel 作业；
业务模块继续保留原状态机，公共任务表只作为文件、进度、租约和结果的权威入口。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class ImportJob(PKMixin, TenantMixin, CommonMixin, Base):
    """t_import_job：跨模块统一导入任务。"""

    __tablename__ = "t_import_job"

    module_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    import_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_file_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    adapter_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="VALIDATED", index=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operator_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    operator_name: Mapped[str | None] = mapped_column(String(100))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    lease_token: Mapped[str | None] = mapped_column(String(96))
    lease_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_receipt_file_id: Mapped[int | None] = mapped_column(BigInteger)
    credential_receipt_file_id: Mapped[int | None] = mapped_column(BigInteger)
    source_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "adapter_type", "adapter_ref",
            name="uk_import_job_adapter_ref",
        ),
        Index("ix_import_job_list", "tenant_id", "status", "created_at", "id"),
        Index("ix_import_job_owner", "tenant_id", "operator_id", "created_at"),
    )


class ImportRowError(PKMixin, TenantMixin, CommonMixin, Base):
    """t_import_row_error：服务端权威预检错误，不信任前端回传 rows。"""

    __tablename__ = "t_import_row_error"

    import_job_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    sheet_name: Mapped[str | None] = mapped_column(String(100))
    row_no: Mapped[int | None] = mapped_column(Integer)
    field_code: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_snapshot_json: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        Index("ix_import_row_error_job_row", "tenant_id", "import_job_id", "row_no"),
    )


class ExportJob(PKMixin, TenantMixin, CommonMixin, Base):
    """t_export_job：系统生成文件、错误回执和凭据回执的统一生命周期。"""

    __tablename__ = "t_export_job"

    module_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    export_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    purpose: Mapped[str | None] = mapped_column(String(500))
    adapter_type: Mapped[str | None] = mapped_column(String(50), index=True)
    adapter_ref: Mapped[str | None] = mapped_column(String(128))
    filter_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    data_scope_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_object_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    downloaded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    operator_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "adapter_type", "adapter_ref", "export_type",
            name="uk_export_job_adapter_ref",
        ),
        Index("ix_export_job_list", "tenant_id", "status", "created_at", "id"),
        Index("ix_export_job_owner", "tenant_id", "operator_id", "created_at"),
    )
