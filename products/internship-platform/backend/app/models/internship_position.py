"""岗位实习中心 · 唯一 canonical 岗位库。

E 系列只对现有 InternshipPosition 做 additive campaign/source scope；历史岗位
campaign_id 保持 NULL，绝不反推旧招聘季。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipPosition(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_internship_position"
    __table_args__ = (
        Index("ix_intern_position_campaign_catalog", "tenant_id", "campaign_id", "status", "company_id", "is_deleted"),
    )

    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="→ t_emp_company.id")
    company_name: Mapped[str | None] = mapped_column(String(200), comment="冗余展示名")
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_internship_batch.id")
    campaign_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_internship_recruitment_campaign.id；历史岗位保持 NULL")
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="SCHOOL", comment="SCHOOL/ENTERPRISE")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), comment="岗位类别")
    major_requirement: Mapped[str | None] = mapped_column(String(200), comment="专业要求")
    grade_requirement: Mapped[str | None] = mapped_column(String(100), comment="年级要求")
    work_location: Mapped[str | None] = mapped_column(String(200), comment="工作地点")
    geofence_lat: Mapped[float | None] = mapped_column(Float, comment="岗位围栏中心纬度")
    geofence_lng: Mapped[float | None] = mapped_column(Float, comment="岗位围栏中心经度")
    geofence_radius_m: Mapped[int | None] = mapped_column(Integer, comment="岗位围栏半径(米)")
    salary_range: Mapped[str | None] = mapped_column(String(50), comment="薪资区间")
    subsidy: Mapped[str | None] = mapped_column(String(50), comment="补贴")
    headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="岗位容量")
    allocated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已分配人数（最终落岗 Authority 写入）")
    mentor_contact_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    mentor_name: Mapped[str | None] = mapped_column(String(100))
    risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_note: Mapped[str | None] = mapped_column(String(500))
    daily_hours: Mapped[float | None] = mapped_column(Float)
    weekly_hours: Mapped[float | None] = mapped_column(Float)
    shift_type: Mapped[str | None] = mapped_column(String(30))
    night_shift: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    overtime_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rest_days: Mapped[str | None] = mapped_column(String(50))
    rest_days_per_week: Mapped[float | None] = mapped_column(Float)
    remuneration_type: Mapped[str | None] = mapped_column(String(30))
    remuneration_amount: Mapped[float | None] = mapped_column(Float)
    remuneration_cycle: Mapped[str | None] = mapped_column(String(30))
    accommodation_provided: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    meal_provided: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hazardous_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    special_equipment: Mapped[str | None] = mapped_column(String(200))
    work_content: Mapped[str | None] = mapped_column(Text)
    work_address: Mapped[str | None] = mapped_column(String(300))
    prohibited_reason: Mapped[str | None] = mapped_column(String(500))
    rights_status: Mapped[str | None] = mapped_column(String(30))
    rights_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    rights_rule_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    remark: Mapped[str | None] = mapped_column(String(500))
    publish_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))
