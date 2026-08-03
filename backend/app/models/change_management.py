"""PLAT-11 变更、发布、兼容性、灰度与回滚。

平台级实体（一次变更横跨多个租户/服务），不经过 _tid()。冻结窗口判定
一部分复用既有 t_calendar_window（各校考试/迎新/实习/毕设窗口，
academic_calendar_service.py 已经维护，不重复造一套按校配置的日历）；
t_maintenance_window 只登记平台自己声明的、不挂靠任何单一学校日历的
全局冻结期（比如"春节假期代码冻结"），两者是互补关系不是重复。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class ChangeRequest(PKMixin, CommonMixin, Base):
    """t_change_request 变更请求主记录。"""
    __tablename__ = "t_change_request"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    change_type: Mapped[str] = mapped_column(
        String(24), nullable=False,
        comment="CODE/MIGRATION/PLATFORM_CONFIG/PACKAGE/COMMON_FOUNDATION/HOTFIX")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", index=True,
        comment="DRAFT/ASSESSED/APPROVED/SCHEDULED/IMPLEMENTING/VERIFIED/FAILED/ROLLED_BACK")
    is_emergency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_irreversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    git_sha: Mapped[str | None] = mapped_column(String(64))
    pr_url: Mapped[str | None] = mapped_column(String(500))
    ci_evidence_json: Mapped[dict | None] = mapped_column(JSON)
    min_client_version: Mapped[str | None] = mapped_column(String(30))
    package_codes_json: Mapped[list | None] = mapped_column(JSON)
    affected_service_codes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rollback_plan: Mapped[str | None] = mapped_column(String(2000))
    requested_by: Mapped[int | None] = mapped_column(BigInteger)
    approved_by: Mapped[int | None] = mapped_column(BigInteger)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(1000))


class ChangeImpact(PKMixin, CommonMixin, Base):
    """t_change_impact 变更影响快照（评估时冻结一次，不随后续依赖图变化改写）。"""
    __tablename__ = "t_change_impact"
    __table_args__ = (UniqueConstraint("change_id", "tenant_id", name="uk_change_impact_scope"),)

    change_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    impact_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="DIRECT/INDIRECT")


class ChangeExecution(PKMixin, CommonMixin, Base):
    """t_change_execution 灰度批次执行记录：一个变更可以有多个递增的 wave。"""
    __tablename__ = "t_change_execution"
    __table_args__ = (UniqueConstraint("change_id", "wave_no", name="uk_change_execution_wave"),)

    change_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    wave_no: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_ids_json: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="PENDING/RUNNING/SUCCEEDED/FAILED/ROLLED_BACK")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(String(1000))


class MaintenanceWindow(PKMixin, CommonMixin, Base):
    """t_maintenance_window 平台声明的全局冻结期（不挂靠任何单一学校日历）。"""
    __tablename__ = "t_maintenance_window"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
