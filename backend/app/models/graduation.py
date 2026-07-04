"""毕业设计域模型（P7-GRADUATION）。t_gd_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class GraduationStudent(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_student"
    student_no: Mapped[str | None] = mapped_column(String(50), index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    class_id: Mapped[str | None] = mapped_column(String(50))
    class_name: Mapped[str | None] = mapped_column(String(100))
    topic_title: Mapped[str | None] = mapped_column(String(300))
    topic_source: Mapped[str | None] = mapped_column(String(100))
    advisor_name: Mapped[str | None] = mapped_column(String(100))
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="TOPIC_SELECTING")
    material_summary: Mapped[str | None] = mapped_column(String(200))
    plagiarism_rate: Mapped[str | None] = mapped_column(String(20))
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="NONE")
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    midterm_conclusion: Mapped[str | None] = mapped_column(String(100))
    defense_group: Mapped[str | None] = mapped_column(String(100))
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class GraduationTopic(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_topic"
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    advisor_name: Mapped[str | None] = mapped_column(String(100))
    major_name: Mapped[str | None] = mapped_column(String(100))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_CONFIRM")
    students_json: Mapped[list | None] = mapped_column(JSON)
    disabled_note: Mapped[str | None] = mapped_column(String(300))


class GraduationProposal(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_proposal"
    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version: Mapped[str | None] = mapped_column(String(20))
    is_resubmit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submit_at: Mapped[datetime | None] = mapped_column(DateTime)
    background: Mapped[str | None] = mapped_column(String(2000))
    plan: Mapped[str | None] = mapped_column(String(2000))
    outcome: Mapped[str | None] = mapped_column(String(2000))
    attachments_json: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_comment: Mapped[str | None] = mapped_column(String(500))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationFinal(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_final"
    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    final_type: Mapped[str] = mapped_column(String(20), nullable=False, default="初稿")
    version: Mapped[str | None] = mapped_column(String(20))
    submit_at: Mapped[datetime | None] = mapped_column(DateTime)
    plagiarism_rate: Mapped[str | None] = mapped_column(String(20))
    plagiarism_status: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_comment: Mapped[str | None] = mapped_column(String(500))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationDefenseGroup(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_defense_group"
    group_name: Mapped[str] = mapped_column(String(50), nullable=False)
    defense_date: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(100))
    chair: Mapped[str | None] = mapped_column(String(100))
    members_json: Mapped[list | None] = mapped_column(JSON)
    secretary: Mapped[str | None] = mapped_column(String(100))
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict: Mapped[str | None] = mapped_column(String(300))
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GraduationAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_gd_audit_trail"
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(200))
    after_val: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
