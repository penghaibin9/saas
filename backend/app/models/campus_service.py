"""在校服务域模型（P7-CAMPUS-SERVICE）。t_cs_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class CsServiceStudent(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_cs_service_student"
    student_no: Mapped[str | None] = mapped_column(String(50), index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10))
    college_name: Mapped[str | None] = mapped_column(String(100))
    major_name: Mapped[str | None] = mapped_column(String(100))
    class_id: Mapped[str | None] = mapped_column(String(50))
    class_name: Mapped[str | None] = mapped_column(String(100))
    grade: Mapped[str | None] = mapped_column(String(20))
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    id_card_encrypted: Mapped[str | None] = mapped_column(String(500))
    counselor: Mapped[str | None] = mapped_column(String(100))
    building: Mapped[str | None] = mapped_column(String(100))
    room: Mapped[str | None] = mapped_column(String(50))
    care_level: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL")
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="LOW")
    mental_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class CsLeave(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_cs_leave"
    code: Mapped[str | None] = mapped_column(String(50))
    cs_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    leave_type: Mapped[str] = mapped_column(String(50), nullable=False, default="PERSONAL")
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    duration: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW")
    apply_time: Mapped[datetime | None] = mapped_column(DateTime)
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(String(500))
    # ── 13A-P2 加列（全 nullable，双状态列并行；旧列语义不动，见 P0 §4.2 集成①）──
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="直连 t_student_profile.id")
    affairs_status: Mapped[str | None] = mapped_column(String(50), index=True, comment="13A 14 态真相列")
    days: Mapped[float | None] = mapped_column(Numeric(5, 1), comment="数值天数，审批层级分流依据")
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    expected_return_at: Mapped[datetime | None] = mapped_column(DateTime)
    actual_return_at: Mapped[datetime | None] = mapped_column(DateTime)
    parent_notify: Mapped[bool | None] = mapped_column(Boolean, default=False)
    overdue_pushed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="逾期扫描幂等标记")


class CsGrant(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_cs_grant"
    code: Mapped[str | None] = mapped_column(String(50))
    cs_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    grant_type: Mapped[str] = mapped_column(String(50), nullable=False, default="SCHOLARSHIP")
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)
    apply_reason: Mapped[str | None] = mapped_column(String(500))
    material_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW")
    apply_time: Mapped[datetime | None] = mapped_column(DateTime)
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(String(500))
    current_node: Mapped[str | None] = mapped_column(String(100))


class CsDormRecord(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_cs_dorm_record"
    cs_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    building: Mapped[str | None] = mapped_column(String(100))
    room: Mapped[str | None] = mapped_column(String(50))
    bed: Mapped[str | None] = mapped_column(String(20))
    checkin_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="IN")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")


class CsDormException(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_cs_dorm_exception"
    code: Mapped[str | None] = mapped_column(String(50))
    cs_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    exc_type: Mapped[str] = mapped_column(String(50), nullable=False, default="NIGHT_OUT")
    happen_time: Mapped[datetime | None] = mapped_column(DateTime)
    detail: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_HANDLE")
    handler: Mapped[str | None] = mapped_column(String(100))
    handle_note: Mapped[str | None] = mapped_column(String(500))
    handle_time: Mapped[datetime | None] = mapped_column(DateTime)


class CsDiscipline(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_cs_discipline"
    code: Mapped[str | None] = mapped_column(String(50))
    cs_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    disc_type: Mapped[str] = mapped_column(String(50), nullable=False, default="WARNING")
    reason: Mapped[str | None] = mapped_column(String(500))
    decide_date: Mapped[datetime | None] = mapped_column(DateTime)
    doc_no: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="EFFECTIVE")
    revoke_date: Mapped[datetime | None] = mapped_column(DateTime)
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))
    # ── 13A-P4 加列（nullable）：投影来源回链，便于一致性对账与回滚清理；存量手工行为 NULL ──
    source_case_id: Mapped[int | None] = mapped_column(BigInteger, index=True,
                                                       comment="t_affairs_discipline_case 投影来源")


class CsWorkOrder(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_cs_work_order"
    code: Mapped[str | None] = mapped_column(String(50))
    cs_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    wo_type: Mapped[str] = mapped_column(String(50), nullable=False, default="CONSULT")
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="MEDIUM")
    handler: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_HANDLE")
    detail: Mapped[str | None] = mapped_column(String(1000))
    close_time: Mapped[datetime | None] = mapped_column(DateTime)
    trail_json: Mapped[list | None] = mapped_column(JSON)


class CsMentalRecord(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_cs_mental_record"
    cs_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL")
    last_follow_time: Mapped[datetime | None] = mapped_column(DateTime)
    next_follow_time: Mapped[datetime | None] = mapped_column(DateTime)
    summary: Mapped[str | None] = mapped_column(String(500))
    counselor_note: Mapped[str | None] = mapped_column(String(1000), comment="涉密：非授权角色不返回")
    operator: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PROCESSING")


class CsAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_cs_audit_trail"
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(200))
    after_val: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
