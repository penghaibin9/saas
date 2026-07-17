"""审计（冻结册 §16：append-only，无 is_deleted/updated_*/version，留存 ≥3 年；敏感字段只存摘要+hash）。
第一批：t_security_audit_log（安全审计）+ t_export_task（导出留痕 §17.3/17.4）。
导入留痕由 models/student.StudentImportBatch（t_student_import_batch）承担。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class SecurityAuditLog(PKMixin, TenantMixin, Base):
    """t_security_audit_log 安全审计——登录/登出/身份切换/越权/敏感查看/下载/导入/导出/删除等。append-only。"""
    __tablename__ = "t_security_audit_log"
    __table_args__ = (
        Index("ix_audit_tenant_created_id", "tenant_id", "created_at", "id"),
        Index("ix_audit_tenant_operator_created", "tenant_id", "operator_id", "created_at"),
    )

    operator_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    operator_name: Mapped[str | None] = mapped_column(String(100))
    current_role: Mapped[str | None] = mapped_column(String(100))
    data_scope: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100), nullable=False, comment="LOGIN/EXPORT/SENSITIVE_VIEW/...")
    resource: Mapped[str | None] = mapped_column(String(200))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    trace_id: Mapped[str | None] = mapped_column(String(100), index=True, comment="= 响应 traceId / request_id")
    request_method: Mapped[str | None] = mapped_column(String(10))
    request_path: Mapped[str | None] = mapped_column(String(500))
    result: Mapped[str | None] = mapped_column(String(50), comment="SUCCESS/FAIL/DENIED")
    detail_json: Mapped[dict | None] = mapped_column(JSON, comment="敏感内容只存摘要+hash，禁止明文")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class ExportTask(PKMixin, TenantMixin, CommonMixin, Base):
    """t_export_task 导出任务留痕（模式/条件/字段清单/数量/文件hash/状态，§17.3）。"""
    __tablename__ = "t_export_task"

    export_mode: Mapped[str] = mapped_column(String(50), nullable=False, comment="LIST/ENCRYPTED_ARCHIVE/DESENSITIZED")
    module_code: Mapped[str | None] = mapped_column(String(50))
    condition_json: Mapped[dict | None] = mapped_column(JSON)
    field_list_json: Mapped[dict | None] = mapped_column(JSON)
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    purpose: Mapped[str | None] = mapped_column(String(500), comment="用途（必填 ≥5 字）")
    file_id: Mapped[int | None] = mapped_column(BigInteger)
    file_hash: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="CREATED",
                                        comment="CREATED/RUNNING/SUCCESS/FAILED")
    remark: Mapped[str | None] = mapped_column(String(500))
