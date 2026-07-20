"""实施与预设中心：项目、配置段、安装快照和上线检查。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class SystemImplementationProject(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_system_implementation_project"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_no", name="uk_sys_impl_project_no"),
        Index("ix_sys_impl_project_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_no: Mapped[str] = mapped_column(String(50), nullable=False)
    project_name: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_code: Mapped[str] = mapped_column(String(50), nullable=False, default="HIGHER_VOCATIONAL")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="CONFIGURING")
    owner_id: Mapped[int | None] = mapped_column(BigInteger)
    change_source_installation_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    target_date: Mapped[date | None] = mapped_column(Date)
    preview_json: Mapped[dict | None] = mapped_column(JSON)
    preview_hash: Mapped[str | None] = mapped_column(String(64))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    accepted_by: Mapped[int | None] = mapped_column(BigInteger)
    acceptance_comment: Mapped[str | None] = mapped_column(String(500))
    acceptance_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    acceptance_summary: Mapped[dict | None] = mapped_column(JSON)


class SystemImplementationSection(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_system_implementation_section"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "section_code", name="uk_sys_impl_section"),
        Index("ix_sys_impl_section_project", "tenant_id", "project_id"),
    )

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    section_code: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="RECOMMENDED")
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CONFIGURED")


class SystemPresetInstallation(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_system_preset_installation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "installation_no", name="uk_sys_preset_install_no"),
        Index("ix_sys_preset_install_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    installation_no: Mapped[str] = mapped_column(String(50), nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False, default="INITIAL")
    source_profile: Mapped[str] = mapped_column(String(50), nullable=False)
    source_version: Mapped[str] = mapped_column(String(30), nullable=False, default="2026.1")
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="APPLIED")
    reason: Mapped[str | None] = mapped_column(String(500))
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class SystemImplementationCheck(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_system_implementation_check"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "check_code", name="uk_sys_impl_check"),
        Index("ix_sys_impl_check_project", "tenant_id", "project_id"),
    )

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_code: Mapped[str] = mapped_column(String(80), nullable=False)
    category_code: Mapped[str] = mapped_column(String(50), nullable=False)
    check_name: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="BLOCKER")
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    owner_role: Mapped[str | None] = mapped_column(String(50))
    confirmed_by: Mapped[int | None] = mapped_column(BigInteger)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    comment: Mapped[str | None] = mapped_column(Text)


class SystemBusinessRelationBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """开户关系安装批次；候选和人工决定持久化，业务主表仍是关系事实源。"""
    __tablename__ = "t_system_business_relation_batch"
    __table_args__ = (UniqueConstraint("tenant_id", "batch_no", name="uk_sys_relation_batch_no"),)

    batch_no: Mapped[str] = mapped_column(String(60), nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_import_batch_no: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DISCOVERED", index=True,
                                        comment="DISCOVERED/CONFIRMED/APPLIED/ROLLED_BACK")
    candidates_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decisions_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime)


class SystemBusinessRelationInstallItem(PKMixin, TenantMixin, CommonMixin, Base):
    """关系安装审计/回滚账本；只记录实施中心对真实主表做过的字段级变更。"""
    __tablename__ = "t_system_business_relation_install_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "relation_key", name="uk_sys_relation_install_key"),
    )

    relation_batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    relation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subject_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    object_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    context_ref: Mapped[str | None] = mapped_column(String(120))
    target_table: Mapped[str] = mapped_column(String(80), nullable=False)
    target_row_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    before_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    after_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="APPLIED", index=True,
                                        comment="APPLIED/ROLLED_BACK/SUPERSEDED")
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime)
    rollback_reason: Mapped[str | None] = mapped_column(String(500))
