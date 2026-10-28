"""审计（冻结册 §16：append-only，无 is_deleted/updated_*/version，留存 ≥3 年；敏感字段只存摘要+hash）。
第一批：t_security_audit_log（安全审计）+ t_export_task（导出留痕 §17.3/17.4）。
导入留痕由 models/student.StudentImportBatch（t_student_import_batch）承担。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class SecurityAuditLog(PKMixin, TenantMixin, Base):
    """t_security_audit_log 安全审计——登录/登出/身份切换/越权/敏感查看/下载/导入/导出/删除等。append-only。"""
    __tablename__ = "t_security_audit_log"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_event_id", name="uk_security_audit_source_event"),
        Index("ix_audit_tenant_created_id", "tenant_id", "created_at", "id"),
        Index("ix_audit_tenant_operator_created", "tenant_id", "operator_id", "created_at"),
    )

    source_event_id: Mapped[str | None] = mapped_column(String(64), comment="Canonical outbox event identity")
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
