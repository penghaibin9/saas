"""数字迎新域模型（P7-ORIENTATION）。t_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, CheckConstraint, DateTime, Index,
                        Integer, Numeric, String, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class OrientationStudent(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_student 新生报到台账。"""
    __tablename__ = "t_orientation_student"
    __table_args__ = (
        UniqueConstraint("tenant_id", "admission_no", name="uk_ori_admission_no"),
        UniqueConstraint("tenant_id", "student_no", name="uk_ori_reserved_student_no"),
        UniqueConstraint("tenant_id", "batch_id", "source_type", "source_record_id",
                         name="uk_ori_batch_source_record"),
        Index("ix_ori_student_tenant_profile_active", "tenant_id", "student_id", "is_deleted"),
        Index("ix_ori_student_batch_active", "tenant_id", "batch_id", "is_deleted"),
        Index("ix_ori_student_org_active", "tenant_id", "college_id", "major_id", "class_id", "is_deleted"),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                          comment="迎新批次 Authority → t_orientation_batch.id")
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="关联 t_student_profile.id（可空）")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    admission_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="录取编号")
    student_no: Mapped[str | None] = mapped_column(
        String(50), comment="学校预分配正式学号；新生自助激活时作为学生主档与登录名 Authority"
    )
    gender: Mapped[str | None] = mapped_column(String(10))
    college_name: Mapped[str | None] = mapped_column(String(100))
    major_name: Mapped[str | None] = mapped_column(String(100))
    college_id: Mapped[int | None] = mapped_column(BigInteger, comment="稳定学院 ID → t_college.id")
    major_id: Mapped[int | None] = mapped_column(BigInteger, comment="稳定专业 ID → t_major.id")
    class_id: Mapped[int | None] = mapped_column(BigInteger, comment="稳定班级 ID → t_class.id")
    class_ref_legacy: Mapped[str | None] = mapped_column(String(50),
                                                        comment="O1 前字符串班级引用，只读兼容快照")
    class_name: Mapped[str | None] = mapped_column(String(100))
    grade: Mapped[str | None] = mapped_column(String(20))
    admission_type: Mapped[str | None] = mapped_column(String(50), comment="录取类型")
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
    source_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                             comment="MANUAL/DOMAIN_IMPORT/LEGACY_BACKFILL")
    source_record_id: Mapped[str] = mapped_column(String(200), nullable=False,
                                                  comment="批次内来源业务键")
    identity_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="UNLINKED",
        comment="UNLINKED/LINKED；是否已绑定 StudentProfile",
    )


class OrientationActivationChallenge(PKMixin, TenantMixin, CommonMixin, Base):
    """新生自助激活的一次性身份核验凭证；不保存身份证尾号或微信 openid。"""
    __tablename__ = "t_orientation_activation_challenge"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "orientation_student_id", name="uk_ori_activation_student"
        ),
        UniqueConstraint("token_hash", name="uk_ori_activation_token_hash"),
        Index("ix_ori_activation_expiry", "status", "expires_at"),
    )

    orientation_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    client_nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="VERIFIED",
        comment="VERIFIED/COMPLETED/EXPIRED",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    client_request_id: Mapped[str | None] = mapped_column(String(100))
    bound_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    wechat_bound: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OrientationO1BackfillIssue(Base):
    """O1 无法自动判定的旧班级引用；只读迁移对账清单。"""
    __tablename__ = "t_orientation_o1_backfill_issue"

    orientation_student_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    issue_code: Mapped[str] = mapped_column(String(50), nullable=False)
    legacy_class_ref: Mapped[str | None] = mapped_column(String(50))
    detail: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class GreenChannelApplication(PKMixin, TenantMixin, CommonMixin, Base):
    """t_green_channel_application 绿色通道申请。"""
    __tablename__ = "t_green_channel_application"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_request_id", name="uk_ori_green_client_request"),
        CheckConstraint(
            "status IN ('SUBMITTED','REVIEWING','APPROVED','RETURNED','REJECTED','WITHDRAWN')",
            name="ck_ori_green_status",
        ),
        CheckConstraint("apply_amount >= 0", name="ck_ori_green_amount"),
        Index("ix_ori_green_student_status", "tenant_id", "student_id", "status", "is_deleted"),
    )

    ori_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, comment="稳定学生 Authority → t_student_profile.id；旧未绑定记录可空"
    )
    client_request_id: Mapped[str | None] = mapped_column(
        String(100), comment="学生端提交幂等号；旧记录可空"
    )
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
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "client_submission_id", name="uk_ori_material_client_submission"
        ),
        CheckConstraint(
            "status IN ('UPLOADED','APPROVED','RETURNED','REJECTED')",
            name="ck_ori_material_status",
        ),
        CheckConstraint("submission_no > 0", name="ck_ori_material_submission_no"),
        Index(
            "ix_ori_material_student_current",
            "tenant_id", "student_id", "material_type", "is_current", "is_deleted",
        ),
    )

    ori_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, comment="稳定学生 Authority → t_student_profile.id；历史未绑定可空"
    )
    material_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                               comment="ID_CARD/ADMISSION_LETTER/PHOTO/ARCHIVE/AID_PROOF")
    file_name: Mapped[str | None] = mapped_column(String(300))
    submission_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supersedes_material_id: Mapped[int | None] = mapped_column(BigInteger)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="LEGACY_BACKFILL",
        comment="LEGACY_BACKFILL/STUDENT_SELF_SERVICE",
    )
    client_submission_id: Mapped[str | None] = mapped_column(String(100))
    asset_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    file_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    submit_time: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="UPLOADED",
                                        comment="UPLOADED/APPROVED/RETURNED/REJECTED")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(String(500))


class OrientationArrivalPlan(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_arrival_plan 学生预报到到校计划 Authority（每名迎新学生一行）。"""
    __tablename__ = "t_orientation_arrival_plan"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "ori_student_id", name="uk_ori_arrival_student"
        ),
        CheckConstraint(
            "arrival_mode IN ('TRAIN','AIR','COACH','SELF_DRIVE','CITY_TRANSIT','OTHER')",
            name="ck_ori_arrival_mode",
        ),
        CheckConstraint(
            "status IN ('SUBMITTED','CANCELLED')", name="ck_ori_arrival_status"
        ),
        CheckConstraint(
            "companion_count >= 0 AND companion_count <= 20",
            name="ck_ori_arrival_companion_count",
        ),
        CheckConstraint(
            "status <> 'SUBMITTED' OR submitted_at IS NOT NULL",
            name="ck_ori_arrival_submit_time",
        ),
        Index(
            "ix_ori_arrival_student_profile",
            "tenant_id", "student_id", "status", "is_deleted",
        ),
    )

    ori_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True, comment="稳定学生 Authority → t_student_profile.id"
    )
    arrival_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    planned_arrival_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    station_name: Mapped[str | None] = mapped_column(String(200))
    transport_no: Mapped[str | None] = mapped_column(String(100))
    pickup_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    companion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class OrientationMaterialRequirement(PKMixin, TenantMixin, CommonMixin, Base):
    """冻结流程版本的材料要求；资格引擎只读取此表，不在前端硬编码必交材料。"""
    __tablename__ = "t_orientation_material_requirement"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "flow_version_id", "material_type",
            name="uk_ori_material_requirement_type",
        ),
        CheckConstraint("sort_order >= 0", name="ck_ori_material_requirement_sort"),
        Index(
            "ix_ori_material_requirement_flow",
            "tenant_id", "flow_version_id", "required", "is_deleted",
        ),
    )

    flow_version_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="冻结流程版本 → t_orientation_flow_version.id"
    )
    material_type: Mapped[str] = mapped_column(String(50), nullable=False)
    material_name: Mapped[str] = mapped_column(String(100), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_scan_clean: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allowed_exts_json: Mapped[list | None] = mapped_column(JSON)
    max_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DEFAULT_BACKFILL",
        comment="DEFAULT_BACKFILL/MANUAL",
    )


class OrientationPaymentAccount(PKMixin, TenantMixin, CommonMixin, Base):
    """迎新缴费当前事实；OrientationStudent 金额/状态仅为兼容投影。"""
    __tablename__ = "t_orientation_payment_account"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "orientation_student_id", name="uk_ori_payment_student"
        ),
        UniqueConstraint(
            "tenant_id", "source_type", "source_biz_id", name="uk_ori_payment_source"
        ),
        CheckConstraint(
            "status IN ('UNPAID','PARTIAL','PAID','WAIVED','DEFERRED')",
            name="ck_ori_payment_status",
        ),
        CheckConstraint(
            "source_type IN ('FINANCE_SYNC','MANUAL_VERIFIED','LEGACY_BACKFILL')",
            name="ck_ori_payment_source_type",
        ),
        CheckConstraint(
            "payable_amount >= 0 AND paid_amount >= 0",
            name="ck_ori_payment_amount",
        ),
        CheckConstraint(
            "status <> 'PAID' OR paid_amount >= payable_amount",
            name="ck_ori_payment_paid_amount",
        ),
        Index(
            "ix_ori_payment_student_status", "tenant_id", "student_id", "status", "is_deleted"
        ),
    )

    orientation_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    payable_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="UNPAID")
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_biz_id: Mapped[str] = mapped_column(String(160), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    verified_by: Mapped[int | None] = mapped_column(BigInteger)


class OrientationQualificationDecision(PKMixin, TenantMixin, CommonMixin, Base):
    """资格引擎最近一次可审计决策；输入事实可重算，前端不得自行裁决。"""
    __tablename__ = "t_orientation_qualification_decision"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "orientation_student_id", name="uk_ori_qualification_student"
        ),
        CheckConstraint(
            "verdict IN ('QUALIFIED','NOT_QUALIFIED','MANUAL_REVIEW')",
            name="ck_ori_qualification_verdict",
        ),
        Index(
            "ix_ori_qualification_verdict",
            "tenant_id", "verdict", "evaluated_at", "is_deleted",
        ),
    )

    orientation_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    blockers_json: Mapped[list | None] = mapped_column(JSON)
    facts_json: Mapped[dict | None] = mapped_column(JSON)
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False, default="O4.1")
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    evaluated_by: Mapped[int | None] = mapped_column(BigInteger)


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
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_no", name="uk_ori_batch_no"),
        CheckConstraint(
            "status = 'DRAFT' OR flow_version_id IS NOT NULL",
            name="ck_ori_batch_active_flow",
        ),
        Index(
            "ix_ori_batch_flow_active", "tenant_id", "flow_version_id", "status", "is_deleted"
        ),
    )

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
    flow_version_id: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="冻结的迎新流程版本 → t_orientation_flow_version.id；草稿发布前可空",
    )
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


class OrientationCheckinToken(PKMixin, TenantMixin, CommonMixin, Base):
    """一次性现场报到凭证状态；只保存 nonce 摘要，不保存可重放的原始 token。"""
    __tablename__ = "t_orientation_checkin_token"
    __table_args__ = (
        UniqueConstraint("tenant_id", "nonce_hash", name="uk_ori_checkin_token_nonce"),
        CheckConstraint(
            "status IN ('ISSUED','CONSUMED','REVOKED','EXPIRED')",
            name="ck_ori_checkin_token_status",
        ),
        CheckConstraint(
            "batch_id > 0 AND orientation_student_id > 0",
            name="ck_ori_checkin_token_subject",
        ),
        Index(
            "ix_ori_checkin_token_student_status",
            "tenant_id", "orientation_student_id", "status", "expires_at", "is_deleted",
        ),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    orientation_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    issued_by: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ISSUED")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    consumed_by: Mapped[int | None] = mapped_column(BigInteger)
    checkin_record_id: Mapped[int | None] = mapped_column(BigInteger)


class OrientationCheckinRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """教师对签名凭证完成 preflight 后形成的唯一现场报到事实。"""
    __tablename__ = "t_orientation_checkin_record"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "orientation_student_id", name="uk_ori_checkin_record_student"
        ),
        UniqueConstraint("tenant_id", "token_id", name="uk_ori_checkin_record_token"),
        UniqueConstraint("tenant_id", "nonce_hash", name="uk_ori_checkin_record_nonce"),
        CheckConstraint("checkin_method = 'SIGNED_TOKEN'", name="ck_ori_checkin_method"),
        CheckConstraint("status = 'CONFIRMED'", name="ck_ori_checkin_record_status"),
        Index(
            "ix_ori_checkin_record_point_time",
            "tenant_id", "checkin_point_id", "checked_in_at", "is_deleted",
        ),
        Index(
            "ix_ori_checkin_record_operator_time",
            "tenant_id", "checked_in_by", "checked_in_at", "is_deleted",
        ),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    orientation_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checkin_point_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    checked_in_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checkin_method: Mapped[str] = mapped_column(String(30), nullable=False, default="SIGNED_TOKEN")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CONFIRMED")


class OrientationEnrollmentFinalize(PKMixin, TenantMixin, CommonMixin, Base):
    """学院最终确认的幂等事务回执，关联正式学生主档与生命周期阶段。"""
    __tablename__ = "t_orientation_enrollment_finalize"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "orientation_student_id", name="uk_ori_finalize_student"
        ),
        UniqueConstraint("tenant_id", "request_id", name="uk_ori_finalize_request"),
        CheckConstraint("to_stage = 'ENROLLED'", name="ck_ori_finalize_stage"),
        CheckConstraint("status = 'FINALIZED'", name="ck_ori_finalize_status"),
        Index(
            "ix_ori_finalize_profile_time",
            "tenant_id", "student_id", "finalized_at", "is_deleted",
        ),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    orientation_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    student_no_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(50))
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="ENROLLED")
    finalized_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finalized_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="FINALIZED")


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


class OrientationFlowVersion(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_flow_version 可发布、可追溯的迎新流程版本 Authority。"""
    __tablename__ = "t_orientation_flow_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version_no", name="uk_ori_flow_version_no"),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_ori_flow_version_status",
        ),
        CheckConstraint(
            "status <> 'PUBLISHED' OR published_at IS NOT NULL",
            name="ck_ori_flow_version_publish_time",
        ),
        Index(
            "ix_ori_flow_version_status",
            "tenant_id", "status", "is_deleted", "version_no",
        ),
    )

    version_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="租户内递增版本号")
    version_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DRAFT", comment="DRAFT/PUBLISHED/RETIRED"
    )
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="MANUAL/LEGACY_CONFIG_BACKFILL"
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by: Mapped[int | None] = mapped_column(BigInteger)
    remark: Mapped[str | None] = mapped_column(String(500))


class OrientationFlowStep(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_flow_step 某个已冻结流程版本内的步骤定义。"""
    __tablename__ = "t_orientation_flow_step"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "flow_version_id", "step_key", name="uk_ori_flow_step_version_key"
        ),
        CheckConstraint("sort_order >= 0", name="ck_ori_flow_step_sort_order"),
        Index(
            "ix_ori_flow_step_version_order",
            "tenant_id", "flow_version_id", "sort_order", "is_deleted",
        ),
    )

    flow_version_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="流程版本 Authority → t_orientation_flow_version.id"
    )
    step_key: Mapped[str] = mapped_column(String(50), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500))


class OrientationStudentStep(PKMixin, TenantMixin, CommonMixin, Base):
    """t_orientation_student_step 新生步骤状态 Authority；steps_json 仅为兼容投影。"""
    __tablename__ = "t_orientation_student_step"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "orientation_student_id", "step_key",
            name="uk_ori_student_step_key",
        ),
        CheckConstraint(
            "status IN ('NOT_STARTED','IN_PROGRESS','BLOCKED','DONE','WAIVED','NOT_REQUIRED')",
            name="ck_ori_student_step_status",
        ),
        CheckConstraint(
            "status <> 'WAIVED' OR (waived_at IS NOT NULL AND waived_by IS NOT NULL "
            "AND waive_evidence_ref IS NOT NULL AND LENGTH(TRIM(waive_reason)) >= 5)",
            name="ck_ori_student_step_waiver_evidence",
        ),
        Index(
            "ix_ori_student_step_student_status",
            "tenant_id", "orientation_student_id", "status", "is_deleted",
        ),
        Index(
            "ix_ori_student_step_flow_status",
            "tenant_id", "flow_version_id", "status", "is_deleted",
        ),
    )

    orientation_student_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="迎新学生过程实例 → t_orientation_student.id"
    )
    flow_version_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="该学生冻结的流程版本"
    )
    flow_step_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="冻结流程步骤 → t_orientation_flow_step.id"
    )
    step_key: Mapped[str] = mapped_column(String(50), nullable=False, comment="步骤业务键快照")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="NOT_STARTED",
        comment="NOT_STARTED/IN_PROGRESS/BLOCKED/DONE/WAIVED/NOT_REQUIRED",
    )
    status_source: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="LEGACY_STEPS_JSON/PROCESS_FACT/MANUAL_WAIVER/RULE"
    )
    source_biz_id: Mapped[str | None] = mapped_column(String(100))
    blocked_reason: Mapped[str | None] = mapped_column(String(500))
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    waived_at: Mapped[datetime | None] = mapped_column(DateTime)
    waived_by: Mapped[int | None] = mapped_column(BigInteger)
    waive_reason: Mapped[str | None] = mapped_column(String(500))
    waive_evidence_ref: Mapped[str | None] = mapped_column(String(200))


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
