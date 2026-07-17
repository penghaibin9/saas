"""数字迎新域模型（P7-ORIENTATION）。t_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class OrientationStudent(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_student 新生报到台账。"""
    __tablename__ = "t_orientation_student"
    __table_args__ = (
        UniqueConstraint("tenant_id", "admission_no", name="uk_ori_admission_no"),
        Index("ix_ori_student_tenant_profile_active", "tenant_id", "student_id", "is_deleted"),
    )

    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="关联 t_student_profile.id（可空）")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    admission_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="录取编号")
    gender: Mapped[str | None] = mapped_column(String(10))
    college_name: Mapped[str | None] = mapped_column(String(100))
    major_name: Mapped[str | None] = mapped_column(String(100))
    class_id: Mapped[str | None] = mapped_column(String(50))
    class_name: Mapped[str | None] = mapped_column(String(100))
    grade: Mapped[str | None] = mapped_column(String(20))
    phone_encrypted: Mapped[str | None] = mapped_column(String(500), comment="手机号（演示占位明文，响应脱敏）")
    id_card_encrypted: Mapped[str | None] = mapped_column(String(500), comment="身份证（脱敏）")
    origin: Mapped[str | None] = mapped_column(String(100), comment="生源地")
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="ADMITTED")
    report_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_REPORTED")
    payment_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNPAID")
    green_channel_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_APPLIED")
    material_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_UPLOADED")
    dorm_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNASSIGNED")
    building: Mapped[str | None] = mapped_column(String(100))
    room: Mapped[str | None] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="LOW")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))
    counselor: Mapped[str | None] = mapped_column(String(100))
    steps_json: Mapped[dict | None] = mapped_column(JSON, comment="7 环节完成状态 map")
    blocked_step: Mapped[str | None] = mapped_column(String(50))
    blocked_reason: Mapped[str | None] = mapped_column(String(500))
    payable_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)
    paid_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)
    checkin_time: Mapped[datetime | None] = mapped_column(DateTime)
    exception_note: Mapped[str | None] = mapped_column(String(500))


class GreenChannelApplication(PKMixin, TenantMixin, CommonMixin, Base):
    """t_green_channel_application 绿色通道申请。"""
    __tablename__ = "t_green_channel_application"

    ori_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    apply_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="助学贷款/缓缴/减免/分期")
    apply_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)
    submit_time: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED",
                                        comment="SUBMITTED/REVIEWING/APPROVED/RETURNED/REJECTED/WITHDRAWN")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    remark: Mapped[str | None] = mapped_column(String(500))


class OrientationMaterial(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_material 迎新材料审核。"""
    __tablename__ = "t_orientation_material"

    ori_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                               comment="ID_CARD/ADMISSION_LETTER/PHOTO/ARCHIVE/AID_PROOF")
    file_name: Mapped[str | None] = mapped_column(String(300))
    submit_time: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="UPLOADED",
                                        comment="UPLOADED/APPROVED/RETURNED/REJECTED")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(String(500))


class OrientationException(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_exception 迎新异常。"""
    __tablename__ = "t_orientation_exception"

    ori_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                                comment="IDENTITY/PAYMENT/MATERIAL/DORM/NO_SHOW")
    description: Mapped[str | None] = mapped_column(String(500))
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN",
                                        comment="OPEN/PROCESSING/RESOLVED/ESCALATED")
    handler: Mapped[str | None] = mapped_column(String(100))
    last_follow_time: Mapped[datetime | None] = mapped_column(DateTime)


class OrientationExceptionFollowup(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_exception_followup 异常跟进。"""
    __tablename__ = "t_orientation_exception_followup"

    exception_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    follow_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    way: Mapped[str] = mapped_column(String(50), nullable=False, default="PHONE")
    content: Mapped[str | None] = mapped_column(String(1000))
    operator: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")


class OrientationAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """t_orientation_audit_trail 迎新域审计——append-only。"""
    __tablename__ = "t_orientation_audit_trail"

    biz_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                          comment="STUDENT/GREEN_CHANNEL/MATERIAL/DORM/PROGRESS/EXCEPTION/IMPORT/EXPORT")
    biz_id: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(200))
    after_val: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class OrientationBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_batch 迎新批次——组织整轮迎新的时间轴与状态骨架。"""
    __tablename__ = "t_orientation_batch"
    __table_args__ = (UniqueConstraint("tenant_id", "batch_no", name="uk_ori_batch_no"),)

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="批次名称，如 2026 级新生迎新")
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False, comment="批次编号")
    year: Mapped[str | None] = mapped_column(String(20), comment="年级/年份")
    start_date: Mapped[datetime | None] = mapped_column(DateTime, comment="批次开始")
    end_date: Mapped[datetime | None] = mapped_column(DateTime, comment="批次结束")
    report_start_date: Mapped[datetime | None] = mapped_column(DateTime, comment="报到开始")
    report_end_date: Mapped[datetime | None] = mapped_column(DateTime, comment="报到结束")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT",
                                        comment="DRAFT 草稿 / ACTIVE 进行中 / CLOSED 已结束")
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="计划新生数")
    remark: Mapped[str | None] = mapped_column(String(500))


class OrientationCheckinPoint(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_checkin_point 现场报到点。"""
    __tablename__ = "t_orientation_checkin_point"

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="报到点名称")
    location: Mapped[str | None] = mapped_column(String(300), comment="地点")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="接待容量")
    in_charge: Mapped[str | None] = mapped_column(String(100), comment="负责人")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENABLED", comment="ENABLED/DISABLED")
    remark: Mapped[str | None] = mapped_column(String(500))


class OrientationFlowConfig(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_flow_config 报到流程配置——每个环节一行。"""
    __tablename__ = "t_orientation_flow_config"
    __table_args__ = (UniqueConstraint("tenant_id", "step_key", name="uk_ori_flow_step"),)

    step_key: Mapped[str] = mapped_column(String(50), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否必办")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500))


class OrientationNoticeTask(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_notice_task 迎新通知任务——渠道状态/发送结果。"""
    __tablename__ = "t_orientation_notice_task"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(String(2000))
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="INAPP",
                                         comment="INAPP 站内/SMS 短信/EMAIL 邮件/MINIAPP 小程序")
    target_scope: Mapped[str | None] = mapped_column(String(200), comment="目标范围说明")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                        comment="PENDING/SENT/FAILED/DISABLED")
    fail_reason: Mapped[str | None] = mapped_column(String(500))
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OrientationArchive(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_archive 迎新归档批次。"""
    __tablename__ = "t_orientation_archive"

    archive_name: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(100))
    scope: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING", comment="PENDING/DONE")
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_by: Mapped[str | None] = mapped_column(String(100))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))
