"""学业过程域模型（P7-ACADEMIC）。t_acad_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class AcademicStudent(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_student"
    student_no: Mapped[str | None] = mapped_column(String(50), index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    class_id: Mapped[str | None] = mapped_column(String(50))
    class_name: Mapped[str | None] = mapped_column(String(100))
    college_name: Mapped[str | None] = mapped_column(String(100))
    major_name: Mapped[str | None] = mapped_column(String(100))
    grade: Mapped[str | None] = mapped_column(String(20))
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    counselor: Mapped[str | None] = mapped_column(String(100))
    gpa: Mapped[float | None] = mapped_column(Numeric(4, 2), default=0)
    avg_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    obtained_credits: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, default=0)
    required_credits: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, default=120)
    makeup_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retake_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_level: Mapped[str] = mapped_column(String(50), nullable=False, default="NONE")
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    academic_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class AcademicGrade(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_grade"
    acad_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term: Mapped[str | None] = mapped_column(String(50))
    nature: Mapped[str] = mapped_column(String(50), nullable=False, default="REQUIRED")
    credit_value: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False, default=0)
    score: Mapped[int | None] = mapped_column(Integer)
    pass_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    exam_type: Mapped[str] = mapped_column(String(50), nullable=False, default="FINAL")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class AcademicMakeup(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_makeup"
    acad_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term: Mapped[str | None] = mapped_column(String(50))
    origin_score: Mapped[int | None] = mapped_column(Integer)
    exam_date: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_EXAM")
    remind_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class AcademicRetake(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_retake"
    acad_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(200), nullable=False)
    retake_term: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENROLLING")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class AcademicWarning(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_warning"
    code: Mapped[str | None] = mapped_column(String(50))
    acad_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    warn_type: Mapped[str] = mapped_column(String(50), nullable=False, default="MULTI_FAIL")
    level: Mapped[str] = mapped_column(String(50), nullable=False, default="MEDIUM")
    reason: Mapped[str | None] = mapped_column(String(500))
    source_rule: Mapped[str | None] = mapped_column(String(100))
    owner: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_HANDLE")
    trigger_time: Mapped[datetime | None] = mapped_column(DateTime)
    deadline: Mapped[str | None] = mapped_column(String(50))
    remind_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    close_result: Mapped[str | None] = mapped_column(String(500))
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class AcademicIntervention(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_intervention"
    warning_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    way: Mapped[str] = mapped_column(String(50), nullable=False, default="TALK")
    content: Mapped[str | None] = mapped_column(String(1000))
    result: Mapped[str | None] = mapped_column(String(500))
    next_plan: Mapped[str | None] = mapped_column(String(500))
    operator: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    follow_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AcademicAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_acad_audit_trail"
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(200))
    after_val: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
