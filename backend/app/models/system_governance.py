"""系统管理治理扩展落库：临时授权 / 接口凭证 / 同步任务（JSON 文档表）。"""
from __future__ import annotations

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class SystemJsonDoc(PKMixin, TenantMixin, CommonMixin, Base):
    """t_system_json_doc 租户级 JSON 文档（治理类轻量实体，避免为每个能力新建宽表）。"""
    __tablename__ = "t_system_json_doc"
    __table_args__ = (UniqueConstraint("tenant_id", "doc_key", name="uk_system_json_doc_tenant_key"),)

    doc_key: Mapped[str] = mapped_column(String(80), nullable=False, comment="DELEGATIONS/INTEGRATIONS/SYNC_JOBS/MODULE_FEATURES")
    payload: Mapped[dict | None] = mapped_column(JSON, comment="文档内容")
    remark: Mapped[str | None] = mapped_column(String(500))
