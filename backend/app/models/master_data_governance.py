"""SYS-17 主数据责任与数据质量。

治理表只存"问题和证据"，不复制主数据
──────────────────────────────────────
学生、组织、课程、企业的权威数据永远在各自业务表里。这里五张表记的是：
有哪些数据域、谁负责、按什么规则扫、扫出了什么问题、合并前看到过哪些引用。
一旦把主数据本身抄一份进来，它立刻会和业务表对不上，还会诱使管理员在系统管理里
直接改业务事实——那是数据域责任人的职责，不是系统管理员的。

问题去重靠 ``issue_key``（租户内唯一）：同一条问题反复扫描只更新，不堆重复行；
修复后重新扫描时，扫不到即视为已消除，这就是"修复后重新扫描验证"的落点。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Index, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

# 严重度：P0 必须有责任人与 SLA，其余可选
SEVERITY_P0 = "P0"
SEVERITY_P1 = "P1"
SEVERITY_P2 = "P2"
SEVERITY_LEVELS = (SEVERITY_P0, SEVERITY_P1, SEVERITY_P2)

# 问题状态机：OPEN →(指派) ASSIGNED →(处理) RESOLVED →(复扫) VERIFIED
#                └→(例外) EXCEPTED（必须有期限与审批人，到期自动回到 OPEN）
ISSUE_OPEN = "OPEN"
ISSUE_ASSIGNED = "ASSIGNED"
ISSUE_RESOLVED = "RESOLVED"
ISSUE_VERIFIED = "VERIFIED"
ISSUE_EXCEPTED = "EXCEPTED"

MERGE_PREVIEW = "PREVIEW"
MERGE_APPLIED = "APPLIED"
MERGE_REJECTED = "REJECTED"


class DataDomain(PKMixin, TenantMixin, CommonMixin, Base):
    """数据域目录：一个域 = 一类主数据 + 它的权威表 + 归属业务模块。"""

    __tablename__ = "t_data_domain"

    domain_code: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_module: Mapped[str] = mapped_column(String(64), nullable=False, comment="业务归属模块")
    authoritative_table: Mapped[str] = mapped_column(String(128), nullable=False,
                                                     comment="权威数据在哪张表，治理表不复制它")
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "domain_code", name="uk_data_domain_code"),
        Index("idx_data_domain_module", "tenant_id", "owner_module"),
    )


class DataOwner(PKMixin, TenantMixin, CommonMixin, Base):
    """数据域责任人。没有责任人的域不允许启用 P0 规则——P0 没人认领等于没有。"""

    __tablename__ = "t_data_owner"

    domain_code: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_role_code: Mapped[str | None] = mapped_column(String(64))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "domain_code", "owner_user_id", name="uk_data_owner"),
        Index("idx_data_owner_domain", "tenant_id", "domain_code", "status"),
    )


class DataQualityRule(PKMixin, TenantMixin, CommonMixin, Base):
    """质量规则：executor_key 指向真实扫描器，规则不写 SQL 字符串给用户拼。"""

    __tablename__ = "t_data_quality_rule"

    domain_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(24), nullable=False,
                                           comment="DUPLICATE/MISSING/BROKEN_LINK")
    severity: Mapped[str] = mapped_column(String(8), nullable=False, default=SEVERITY_P2)
    executor_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="内置扫描器键")
    sla_hours: Mapped[int | None] = mapped_column(Integer, comment="P0 必填")
    params_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_code", name="uk_data_quality_rule_code"),
        Index("idx_data_quality_rule_domain", "tenant_id", "domain_code", "status"),
    )


class DataQualityIssue(PKMixin, TenantMixin, CommonMixin, Base):
    """一条真实问题。issue_key 是幂等键：同一问题重复扫描只更新，不堆重复行。"""

    __tablename__ = "t_data_quality_issue"

    domain_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    issue_key: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False, default=SEVERITY_P2)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ISSUE_OPEN)
    object_type: Mapped[str | None] = mapped_column(String(64))
    object_id: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, comment="证据，不是主数据副本")
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, comment="按规则 SLA 推算")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[int | None] = mapped_column(BigInteger)
    resolve_note: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[int | None] = mapped_column(BigInteger)
    verify_result: Mapped[str | None] = mapped_column(String(24), comment="GONE/STILL_PRESENT")
    exception_until: Mapped[datetime | None] = mapped_column(DateTime)
    exception_reason: Mapped[str | None] = mapped_column(String(500))
    exception_approved_by: Mapped[int | None] = mapped_column(BigInteger)
    scan_batch_no: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("tenant_id", "issue_key", name="uk_data_quality_issue_key"),
        Index("idx_data_quality_issue_status", "tenant_id", "status", "severity"),
        Index("idx_data_quality_issue_domain", "tenant_id", "domain_code", "rule_code"),
        Index("idx_data_quality_issue_due", "tenant_id", "due_at"),
    )


class MasterMergeEvent(PKMixin, TenantMixin, CommonMixin, Base):
    """主数据合并留痕：先预览引用，再决定。高风险合并不允许自动执行。"""

    __tablename__ = "t_master_merge_event"

    domain_code: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_object_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="保留方")
    merged_object_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="被并方")
    preview_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    references_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="被并方的全部引用")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MERGE_PREVIEW)
    reason: Mapped[str | None] = mapped_column(String(500))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decided_by: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        Index("idx_master_merge_domain", "tenant_id", "domain_code", "status"),
        Index("idx_master_merge_objects", "tenant_id", "primary_object_id", "merged_object_id"),
    )
