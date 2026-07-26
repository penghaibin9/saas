"""公共 Excel 底座 · 通用导入记录模型（t_excel_import_job）。

跨模块共用的导入作业台账：谁、在哪个模块、导了什么文件、结果如何、何时确认。
- 复用共享公共字段：tenant_id + 审计时间 + is_deleted 软删 + version（base.CommonMixin）。
- 导出暂不建 t_excel_export_job（按需求至少落审计即可，见 excel API/service）。

隔离：本表为底座通用表，不与任何具体业务表耦合，module_key/biz_type 仅作标签。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class ExcelImportJob(PKMixin, TenantMixin, CommonMixin, Base):
    """t_excel_import_job 通用 Excel 导入作业记录。"""
    __tablename__ = "t_excel_import_job"

    module_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="模块 key")
    biz_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="业务类型")
    file_name: Mapped[str | None] = mapped_column(String(255), comment="上传文件名")
    file_sha256: Mapped[str | None] = mapped_column(String(64), comment="Original upload SHA-256")
    dry_run_sha256: Mapped[str | None] = mapped_column(String(64), comment="Dry-run result SHA-256")
    preview_token_sha256: Mapped[str | None] = mapped_column(String(64), comment="Preview token SHA-256")
    batch_scope: Mapped[str | None] = mapped_column(String(500), comment="Import batch scope snapshot")
    data_scope_snapshot: Mapped[dict | None] = mapped_column(JSON, comment="Actor data scope snapshot")
    template_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    # 状态机：UPLOADED→VALIDATING→VALIDATED→CONFIRMING→IMPORTED / FAILED / CANCELLED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPLOADED", index=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expected_success_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_file_key: Mapped[str | None] = mapped_column(String(255), comment="错误行文件句柄（预留）")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, comment="操作人 ID")
    operator_name: Mapped[str | None] = mapped_column(String(100), comment="操作人姓名")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="开始校验时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, comment="结束时间")
    confirm_at: Mapped[datetime | None] = mapped_column(DateTime, comment="确认导入时间")
    remark: Mapped[str | None] = mapped_column(String(500))
