"""岗位实习域模型（P7-INTERNSHIP）。对齐 DB 冻结册命名：t_ 前缀 / snake_case / BIGINT PK /
公共字段（tenant_id/created_at/...）。审计链 append-only（AuditTimeMixin）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class InternshipBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_batch 实习批次（组织实习工作的时间轴 + 规则骨架，状态机
    DRAFT草稿 → RUNNING进行中 → CLOSED已结束 → ARCHIVED已归档；VOIDED仅草稿可作废）。"""
    __tablename__ = "t_internship_batch"
    __table_args__ = (UniqueConstraint("tenant_id", "batch_no", name="uk_intern_batch_no"),)

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_year: Mapped[str | None] = mapped_column(String(20), comment="学年，如 2025-2026")
    term: Mapped[str | None] = mapped_column(String(20), comment="学期")
    start_date: Mapped[datetime | None] = mapped_column(DateTime, comment="实习起")
    end_date: Mapped[datetime | None] = mapped_column(DateTime, comment="实习止")
    signup_start_date: Mapped[datetime | None] = mapped_column(DateTime, comment="报名/资格确认窗口起")
    signup_end_date: Mapped[datetime | None] = mapped_column(DateTime, comment="报名/资格确认窗口止")
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="计划实习人数")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT",
                                        comment="DRAFT/RUNNING/CLOSED/ARCHIVED/VOIDED")
    stage_config: Mapped[list | None] = mapped_column(JSON, comment="阶段/时间轴 [{code,name,startDate,endDate}]")
    rules_config: Mapped[dict | None] = mapped_column(
        JSON, comment="规则配置 {checkin/weeklyReport/guidance/evaluation/score}")
    previous_status: Mapped[str | None] = mapped_column(String(50))
    last_transition_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_transition_by: Mapped[str | None] = mapped_column(String(100))
    transition_reason: Mapped[str | None] = mapped_column(String(500))
    archive_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_ARCHIVED",
                                                comment="NOT_ARCHIVED/ARCHIVED")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))
    archive_batch_no: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(String(500))


class InternshipRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_record 学生实习记录（一名学生一个批次一条）。"""
    __tablename__ = "t_internship_record"
    __table_args__ = (UniqueConstraint("tenant_id", "student_id", "batch_id",
                                       name="uk_intern_stu_batch"),)

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True,
                                            comment="= t_student_profile.id")
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    enterprise_name: Mapped[str | None] = mapped_column(String(200), comment="实习单位（冗余展示）")
    position_name: Mapped[str | None] = mapped_column(String(100), comment="岗位（冗余展示）")
    advisor_name: Mapped[str | None] = mapped_column(String(100), comment="校内指导教师")
    enterprise_mentor_name: Mapped[str | None] = mapped_column(String(100), comment="企业导师（冗余展示）")
    # ── 与企业库/岗位库真实关联（additive；分配岗位时回填，退岗时清空）──
    enterprise_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_emp_company.id")
    position_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_internship_position.id")
    mentor_contact_id: Mapped[int | None] = mapped_column(BigInteger, comment="→ t_internship_enterprise_contact.id")
    eligibility_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                                    comment="实习资格 PENDING/QUALIFIED/UNQUALIFIED")
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False, default="NONE",
                                                  comment="实习去向 ASSIGNED/SELF_ARRANGED/EXEMPTED/NONE")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PREPARING",
                                        comment="PREPARING/READY/ONBOARD/ASSESSING/ARCHIVED")
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="NONE",
                                            comment="NONE/LOW/MEDIUM/HIGH")
    intern_start_date: Mapped[datetime | None] = mapped_column(DateTime)
    intern_end_date: Mapped[datetime | None] = mapped_column(DateTime)
    insurance_info: Mapped[str | None] = mapped_column(String(200), comment="实习保险")
    agreement_info: Mapped[str | None] = mapped_column(String(200), comment="三方协议状态")
    remark: Mapped[str | None] = mapped_column(String(500))


class AttendanceException(PKMixin, TenantMixin, CommonMixin, Base):
    """t_attendance_exception 打卡异常（超范围/模拟定位/缺卡）。"""
    __tablename__ = "t_attendance_exception"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                                comment="OUT_OF_RANGE/MOCK_LOCATION/MISSING")
    exception_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    distance_km: Mapped[float | None] = mapped_column(Float, comment="偏离距离(km)")
    gps_accuracy: Mapped[float | None] = mapped_column(Float, comment="定位精度(m)")
    device_risk_flag: Mapped[str | None] = mapped_column(String(50), comment="normal/is_mock")
    address: Mapped[str | None] = mapped_column(String(300))
    student_note: Mapped[str | None] = mapped_column(String(1000), comment="学生说明")
    streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="连续异常天数")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_HANDLE",
                                        comment="PENDING_HANDLE/COMPLETED")
    handle_action: Mapped[str | None] = mapped_column(String(50),
                                                      comment="REASONABLE/ABNORMAL/TO_RISK")
    handle_comment: Mapped[str | None] = mapped_column(String(500))
    handled_by_name: Mapped[str | None] = mapped_column(String(100))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipCheckin(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_checkin 实习每日打卡（真实落库；一天一次，唯一约束兜底并发）。
    企业电子围栏未配置时 result=RECORDED（仅留痕定位），配置后可算 NORMAL/OUT_OF_RANGE。"""
    __tablename__ = "t_internship_checkin"
    __table_args__ = (UniqueConstraint("tenant_id", "internship_id", "checkin_date",
                                       name="uk_internship_checkin_day"),)

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    checkin_date: Mapped[str] = mapped_column(String(10), nullable=False, comment="YYYY-MM-DD")
    checkin_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(300))
    result: Mapped[str] = mapped_column(String(30), nullable=False, default="RECORDED",
                                        comment="RECORDED/NORMAL/OUT_OF_RANGE/NO_LOCATION")
    note: Mapped[str | None] = mapped_column(String(500), comment="学生备注")


class WeeklyReport(PKMixin, TenantMixin, CommonMixin, Base):
    """t_weekly_report 实习周报（支持重交版本）。"""
    __tablename__ = "t_weekly_report"
    __table_args__ = (UniqueConstraint("tenant_id", "internship_id", "week_number",
                                       name="uk_weekly_report_week"),)

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    work_content: Mapped[str | None] = mapped_column(String(2000), comment="本周工作")
    harvest_content: Mapped[str | None] = mapped_column(String(2000), comment="学习收获")
    plan_content: Mapped[str | None] = mapped_column(String(2000), comment="下周计划")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                                comment="版本号，重交自增")
    risk_flag: Mapped[str | None] = mapped_column(String(50), comment="内容风险标记")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW",
                                        comment="PENDING_REVIEW/APPROVED/RETURNED/OVERDUE")
    review_action: Mapped[str | None] = mapped_column(String(50), comment="APPROVE/RETURN")
    review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class RiskRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """t_risk_record 实习风险单（系统预警或人工创建）。"""
    __tablename__ = "t_risk_record"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    risk_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="如 INT-R07")
    risk_title: Mapped[str] = mapped_column(String(200), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="MEDIUM",
                                            comment="HIGH/MEDIUM/LOW")
    source_module: Mapped[str] = mapped_column(String(50), nullable=False, default="system",
                                               comment="system/manual")
    owner_name: Mapped[str | None] = mapped_column(String(100), comment="跟进责任人")
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_HANDLE",
                                        comment="PENDING_HANDLE/PROCESSING/RESOLVED/CLOSED")
    last_follow_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_follow_note: Mapped[str | None] = mapped_column(String(500))


class InternshipAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """t_internship_audit_trail 实习域操作留痕——append-only（无 is_deleted/updated_at/version）。"""
    __tablename__ = "t_internship_audit_trail"

    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                             comment="RECORD/EXCEPTION/REPORT/RISK/BATCH")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(100))
    detail_json: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
