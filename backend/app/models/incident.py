"""PLAT-09 事件、状态页与统一学校通知。

平台级实体（一次事件横跨多个学校），不经过 _tid()。受众快照
（t_incident_tenant）在事件创建时算一次并冻结——之后服务目录的依赖关系
再怎么变，也不会改变"这次事件当时通知了谁"，这正是"一次发布只给受影响
租户"里"受影响"的权威判定时点。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class Incident(PKMixin, CommonMixin, Base):
    """t_incident 平台事件主记录。"""
    __tablename__ = "t_incident"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="P2",
                                          comment="P0/P1/P2/P3")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DETECTED", index=True,
        comment="DETECTED/ACKNOWLEDGED/MITIGATING/MONITORING/RESOLVED")
    affected_service_codes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    commander_user_id: Mapped[int | None] = mapped_column(BigInteger)
    commander_name: Mapped[str | None] = mapped_column(String(100))
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    problem_conversion_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    problem_conversion_requested_by: Mapped[int | None] = mapped_column(BigInteger)


class IncidentTenant(PKMixin, CommonMixin, Base):
    """t_incident_tenant 受影响租户快照（创建事件时冻结一次，不随后续依赖变化改写）。"""
    __tablename__ = "t_incident_tenant"
    __table_args__ = (UniqueConstraint("incident_id", "tenant_id", name="uk_incident_tenant_scope"),)

    incident_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    impact_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="DIRECT/INDIRECT")


class IncidentUpdate(PKMixin, CommonMixin, Base):
    """t_incident_update 事件时间线更新；内部记录与对外学校侧文案分离字段。"""
    __tablename__ = "t_incident_update"
    __table_args__ = (UniqueConstraint("incident_id", "update_seq", name="uk_incident_update_seq"),)

    incident_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    update_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    status_at_update: Mapped[str] = mapped_column(String(20), nullable=False)
    internal_note: Mapped[str | None] = mapped_column(String(2000))
    external_message: Mapped[str] = mapped_column(String(1000), nullable=False)
    template_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    notification_result_json: Mapped[dict | None] = mapped_column(JSON)
