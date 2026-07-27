"""学业过程域模型（P7-ACADEMIC）。t_acad_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class AcademicStudent(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_student"
    __table_args__ = (
        Index("ix_acad_student_tenant_profile_active", "tenant_id", "student_id", "is_deleted"),
    )
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
    """正式成绩事实。

    V2-04 起新写入必须保存稳定课程身份、修读次数和业务来源。展示快照字段继续保留；历史行允许为空，
    通过显式回填治理，禁止迁移时按课程名自动合并。
    """
    __tablename__ = "t_acad_grade"
    __table_args__ = (
        UniqueConstraint("tenant_id", "grade_record_id", name="uk_acad_grade_source_record"),
        UniqueConstraint("tenant_id", "source_biz_type", "source_biz_id", name="uk_acad_grade_source_biz"),
        Index(
            "ix_acad_grade_course_attempt",
            "tenant_id", "acad_student_id", "course_id", "attempt_no", "record_status",
        ),
        Index("ix_acad_grade_course_code", "tenant_id", "course_code", "course_version"),
        Index("ix_acad_grade_grade_task", "tenant_id", "grade_task_id"),
        Index("ix_acad_grade_teaching_task", "tenant_id", "teaching_task_id"),
        Index("ix_acad_grade_teaching_class", "tenant_id", "teaching_class_id"),
        Index("ix_acad_grade_source_biz", "tenant_id", "source_biz_type", "source_biz_id"),
    )
    acad_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="→ t_aa_course.id，具体课程版本行")
    course_code: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="课程代码快照")
    course_version: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="课程库版本快照")
    attempt_no: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="第几次修读；补考/清考继承原修读次数")
    grade_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="→ t_aa_grade_task")
    grade_record_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="→ t_aa_grade_record；正常发布来源唯一")
    source_biz_type: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="MAKEUP/RECOGNITION/EXEMPTION等")
    source_biz_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="业务来源记录ID")
    teaching_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="→ t_aa_teaching_task")
    teaching_class_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="→ t_aa_teaching_class")
    roster_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="发布时采用的正式名单版本")
    course_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term: Mapped[str | None] = mapped_column(String(50))
    nature: Mapped[str] = mapped_column(String(50), nullable=False, default="REQUIRED")
    credit_value: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False, default=0)
    score: Mapped[int | None] = mapped_column(Integer)
    pass_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    exam_type: Mapped[str] = mapped_column(String(50), nullable=False, default="FINAL")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(20), default="LEGACY", comment="LEGACY/PUBLISH/CHANGE/MANUAL")


class AcademicMakeup(PKMixin, TenantMixin, CommonMixin, Base):
    """补考、清考和缓考后续考试名单事实。

    纳入名单时冻结原成绩或缓考来源、稳定课程身份、教学任务和名单版本；发布不再按课程名反查。
    """
    __tablename__ = "t_acad_makeup"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_biz_type", "source_biz_id", name="uk_acad_makeup_source_biz"),
        Index("ix_acad_makeup_origin_grade", "tenant_id", "origin_grade_id"),
        Index("ix_acad_makeup_course_attempt", "tenant_id", "acad_student_id", "course_id", "attempt_no"),
        Index("ix_acad_makeup_teaching_task", "tenant_id", "teaching_task_id"),
        Index("ix_acad_makeup_roster_version", "tenant_id", "roster_version_id"),
    )
    acad_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="MAKEUP", index=True,
        comment="MAKEUP常规补考/CLEARANCE毕业清考/DEFERRED缓考后续考试",
    )
    origin_grade_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="→ t_acad_grade 原失败成绩")
    source_biz_type: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="DEFERRED_EXAM等原始业务")
    source_biz_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    course_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="具体课程版本")
    course_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    course_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_no: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="补考继承原修读次数；缓考冻结当前修读次数")
    teaching_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    teaching_class_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    roster_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    course_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term: Mapped[str | None] = mapped_column(String(50))
    origin_score: Mapped[int | None] = mapped_column(Integer)
    exam_date: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_EXAM")
    remind_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_aa_makeup_batch 补考批次")
    final_score: Mapped[int | None] = mapped_column(Integer, comment="补考最终成绩(计分规则封顶后)")


class AcademicRetake(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_retake"
    acad_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(200), nullable=False)
    retake_term: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENROLLING")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))
    apply_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_aa_retake_apply 重修申请")


class AcademicWarning(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_acad_warning"
    __table_args__ = (
        Index("ix_warning_tenant_student_status", "tenant_id", "acad_student_id", "is_deleted", "status"),
    )
    code: Mapped[str | None] = mapped_column(String(50))
    acad_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    warn_type: Mapped[str] = mapped_column(String(50), nullable=False, default="MULTI_FAIL")
    level: Mapped[str] = mapped_column(String(50), nullable=False, default="MEDIUM")
    reason: Mapped[str | None] = mapped_column(String(500))
    source_rule: Mapped[str | None] = mapped_column(String(100))
    source_code: Mapped[str | None] = mapped_column(String(50), index=True, comment="来源 EXAM_FAIL/CREDIT_GAP…")
    rule_code: Mapped[str | None] = mapped_column(String(50), comment="触发规则编码")
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
