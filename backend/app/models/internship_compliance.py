"""岗位实习 P2 合规证据模型：规则模板、考察、知情确认、安全教育、特殊备案、
应急/事故、豁免、证据包。与 InternshipBatch.rules_config 快照配合，不另建万能 JSON 表。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Float, Integer, String, Text,
                        Index, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipComplianceTemplate(PKMixin, TenantMixin, CommonMixin, Base):
    """学校级合规模板（DRAFT/ACTIVE/RETIRED）；启用后不可原地覆盖，须升版本。"""
    __tablename__ = "t_internship_compliance_template"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_code", "template_version",
                         name="uk_ix_compliance_tpl_ver"),
    )

    template_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT",
                                        comment="DRAFT/ACTIVE/RETIRED")
    config: Mapped[dict | None] = mapped_column(JSON, comment="合规规则 JSON")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by_name: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    change_reason: Mapped[str | None] = mapped_column(String(500))
    remark: Mapped[str | None] = mapped_column(String(500))


class InternshipEnterpriseInspection(PKMixin, TenantMixin, CommonMixin, Base):
    """企业考察/准入证据。"""
    __tablename__ = "t_internship_enterprise_inspection"
    __table_args__ = (
        Index("ix_ix_ent_insp_tenant_company", "tenant_id", "company_id", "is_deleted"),
    )

    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    inspection_type: Mapped[str] = mapped_column(String(30), nullable=False, default="DOCUMENT",
                                                 comment="ONSITE/REMOTE/DOCUMENT")
    inspection_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    inspection_date: Mapped[datetime | None] = mapped_column(DateTime)
    inspectors: Mapped[str | None] = mapped_column(String(200))
    workplace_address: Mapped[str | None] = mapped_column(String(300))
    safety_condition: Mapped[str | None] = mapped_column(String(500))
    accommodation_condition: Mapped[str | None] = mapped_column(String(500))
    mentor_condition: Mapped[str | None] = mapped_column(String(500))
    remuneration_condition: Mapped[str | None] = mapped_column(String(500))
    conclusion: Mapped[str | None] = mapped_column(String(1000))
    risk_items: Mapped[str | None] = mapped_column(Text)
    rectification_items: Mapped[str | None] = mapped_column(Text)
    file_ids: Mapped[list | None] = mapped_column(JSON)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT",
                                        comment="DRAFT/SUBMITTED/APPROVED/REJECTED/EXPIRED")
    review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    rule_version: Mapped[str | None] = mapped_column(String(64))


class InternshipConsent(PKMixin, TenantMixin, CommonMixin, Base):
    """学生/监护人知情确认（含内容快照；已读≠确认）。"""
    __tablename__ = "t_internship_consent"
    __table_args__ = (
        Index("ix_ix_consent_intern", "tenant_id", "internship_id", "consent_type", "is_deleted"),
    )

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(20), nullable=False,
                                              comment="STUDENT/GUARDIAN")
    applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    participant_name: Mapped[str | None] = mapped_column(String(100))
    participant_relation: Mapped[str | None] = mapped_column(String(50))
    identity_masked: Mapped[str | None] = mapped_column(String(64))
    contact_masked: Mapped[str | None] = mapped_column(String(64))
    content_version: Mapped[str | None] = mapped_column(String(64))
    content_snapshot: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    delivery_channel: Mapped[str | None] = mapped_column(String(40))
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmation_method: Mapped[str | None] = mapped_column(String(40))
    device_digest: Mapped[str | None] = mapped_column(String(128))
    client_ip_digest: Mapped[str | None] = mapped_column(String(128))
    confirmed_by_user_id: Mapped[str | None] = mapped_column(String(64))
    confirmed_student_id: Mapped[int | None] = mapped_column(BigInteger)
    guardian_token_hash: Mapped[str | None] = mapped_column(String(64))
    guardian_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    guardian_token_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    guardian_token_revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    file_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING",
        comment="NOT_APPLICABLE/MISSING/PENDING/VALID/REJECTED/EXPIRED/SUPERSEDED/REVOKED")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    rule_version: Mapped[str | None] = mapped_column(String(64))


class InternshipSafetyCourse(PKMixin, TenantMixin, CommonMixin, Base):
    """岗前安全教育课程（按批次/学校模板）。"""
    __tablename__ = "t_internship_safety_course"

    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    course_version: Mapped[str] = mapped_column(String(40), nullable=False, default="v1")
    required_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    passing_score: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    require_commitment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content_snapshot: Mapped[str | None] = mapped_column(Text)
    material_file_ids: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE",
                                        comment="DRAFT/ACTIVE/RETIRED")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)
    rule_version: Mapped[str | None] = mapped_column(String(64))


class InternshipSafetyCompletion(PKMixin, TenantMixin, CommonMixin, Base):
    """学生安全教育完成记录（禁止前端直接传 passed=true 绕过）。"""
    __tablename__ = "t_internship_safety_completion"
    __table_args__ = (
        UniqueConstraint("tenant_id", "internship_id", "course_id",
                         name="uk_ix_safety_completion"),
    )

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_version: Mapped[str] = mapped_column(String(40), nullable=False)
    course_content_snapshot: Mapped[str | None] = mapped_column(Text)
    course_content_hash: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    studied_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    answer_snapshot: Mapped[dict | None] = mapped_column(JSON)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[int | None] = mapped_column(Integer)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    commitment_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    commitment_at: Mapped[datetime | None] = mapped_column(DateTime)
    commitment_content_hash: Mapped[str | None] = mapped_column(String(64))
    commitment_device_digest: Mapped[str | None] = mapped_column(String(128))
    evidence_file_id: Mapped[str | None] = mapped_column(String(64))
    review_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="TEACHER_REVIEW",
        comment="ONLINE_QUIZ/TEACHER_REVIEW")
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(64))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING",
                                        comment="PENDING/PASSED/FAILED/EXPIRED")
    rule_version: Mapped[str | None] = mapped_column(String(64))


class InternshipSpecialFiling(PKMixin, TenantMixin, CommonMixin, Base):
    """跨区域/夜班/高风险等特殊实习备案。"""
    __tablename__ = "t_internship_special_filing"
    __table_args__ = (
        Index("ix_ix_filing_intern", "tenant_id", "internship_id", "is_deleted"),
    )

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    filing_type: Mapped[str] = mapped_column(
        String(40), nullable=False,
        comment="CROSS_PROVINCE/CROSS_CITY/OVERSEAS/HIGH_RISK/NIGHT_SHIFT/SPECIAL_TRADE/MINOR/REMOTE/OTHER")
    applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trigger_reason: Mapped[str | None] = mapped_column(String(500))
    destination_region: Mapped[str | None] = mapped_column(String(200))
    work_address: Mapped[str | None] = mapped_column(String(300))
    risk_description: Mapped[str | None] = mapped_column(Text)
    student_application: Mapped[str | None] = mapped_column(Text)
    guardian_consent_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    college_review_by: Mapped[str | None] = mapped_column(String(100))
    college_review_at: Mapped[datetime | None] = mapped_column(DateTime)
    college_comment: Mapped[str | None] = mapped_column(String(500))
    school_review_by: Mapped[str | None] = mapped_column(String(100))
    school_review_at: Mapped[datetime | None] = mapped_column(DateTime)
    school_comment: Mapped[str | None] = mapped_column(String(500))
    regulator_filing_no: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DRAFT",
        comment="NOT_REQUIRED/DRAFT/PENDING_COLLEGE/PENDING_SCHOOL/APPROVED/REJECTED/WITHDRAWN/EXPIRED/SUPERSEDED")
    approved_by_name: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    file_ids: Mapped[list | None] = mapped_column(JSON)
    rule_version: Mapped[str | None] = mapped_column(String(64))
    superseded_by_id: Mapped[int | None] = mapped_column(BigInteger)


class InternshipRemunerationRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """报酬台账（不代发；可选实发与凭证）。"""
    __tablename__ = "t_internship_remuneration_record"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    position_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    agreed_amount: Mapped[float | None] = mapped_column(Float)
    agreed_cycle: Mapped[str | None] = mapped_column(String(30), comment="MONTHLY/WEEKLY/DAILY/ONCE")
    actual_paid_amount: Mapped[float | None] = mapped_column(Float)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    proof_file_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="AGREED",
                                        comment="AGREED/PARTIAL/PAID/DISCREPANCY/UNCONFIRMED")
    discrepancy: Mapped[str | None] = mapped_column(String(500))
    student_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    rule_version: Mapped[str | None] = mapped_column(String(64))


class InternshipEmergencyPlan(PKMixin, TenantMixin, CommonMixin, Base):
    """企业/批次应急预案。"""
    __tablename__ = "t_internship_emergency_plan"
    __table_args__ = (
        Index("ix_ix_emerg_company", "tenant_id", "company_id", "is_deleted"),
    )

    company_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    plan_name: Mapped[str] = mapped_column(String(200), nullable=False)
    responsible_person: Mapped[str | None] = mapped_column(String(100))
    emergency_contact: Mapped[str | None] = mapped_column(String(100))
    backup_contact: Mapped[str | None] = mapped_column(String(100))
    hospital_or_support: Mapped[str | None] = mapped_column(String(300))
    response_steps: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    file_ids: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT",
                                        comment="DRAFT/PENDING_REVIEW/APPROVED/EXPIRED")
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    rule_version: Mapped[str | None] = mapped_column(String(64))


class InternshipIncident(PKMixin, TenantMixin, CommonMixin, Base):
    """实习事故（与普通 RiskRecord 区分）。"""
    __tablename__ = "t_internship_incident"
    __table_args__ = (
        UniqueConstraint("tenant_id", "incident_no", name="uk_ix_incident_no"),
        Index("ix_ix_incident_batch", "tenant_id", "batch_id", "is_deleted"),
    )

    incident_no: Mapped[str] = mapped_column(String(64), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    internship_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    company_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    risk_id: Mapped[int | None] = mapped_column(BigInteger, comment="联动 RiskRecord.id")
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False, default="OTHER")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM",
                                          comment="LOW/MEDIUM/HIGH/CRITICAL")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)
    injury_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    affected_persons: Mapped[str | None] = mapped_column(String(500))
    reported_by_name: Mapped[str | None] = mapped_column(String(100))
    reported_at: Mapped[datetime | None] = mapped_column(DateTime)
    emergency_action: Mapped[str | None] = mapped_column(Text)
    guardian_notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    school_notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    external_reported_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="REPORTED",
        comment="REPORTED/EMERGENCY_HANDLING/INVESTIGATING/RECTIFYING/PENDING_REVIEW/CLOSED")
    investigation_conclusion: Mapped[str | None] = mapped_column(Text)
    responsibility_conclusion: Mapped[str | None] = mapped_column(Text)
    rectification_plan: Mapped[str | None] = mapped_column(Text)
    rectification_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_by_name: Mapped[str | None] = mapped_column(String(100))
    file_ids: Mapped[list | None] = mapped_column(JSON)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), index=True)
    rule_version: Mapped[str | None] = mapped_column(String(64))


class InternshipComplianceExemption(PKMixin, TenantMixin, CommonMixin, Base):
    """单项合规豁免（有权限/原因/依据/有效期）。"""
    __tablename__ = "t_internship_compliance_exemption"
    __table_args__ = (
        Index("ix_ix_exempt_intern", "tenant_id", "internship_id", "check_code", "is_deleted"),
    )

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    check_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    evidence_file_ids: Mapped[list | None] = mapped_column(JSON)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT",
                                        comment="DRAFT/PENDING_REVIEW/APPROVED/REJECTED/EXPIRED/REVOKED")
    approved_by_name: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    requested_by_name: Mapped[str | None] = mapped_column(String(100))
    requested_by_user_id: Mapped[str | None] = mapped_column(String(64))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    rule_version: Mapped[str | None] = mapped_column(String(64))


class InternshipEvidencePackage(PKMixin, TenantMixin, CommonMixin, Base):
    """监管证据包元数据（文件落文件中心；不可静默改包）。"""
    __tablename__ = "t_internship_evidence_package"
    __table_args__ = (
        Index("ix_ix_evpkg_target", "tenant_id", "package_type", "target_id", "is_deleted"),
    )

    package_type: Mapped[str] = mapped_column(String(20), nullable=False,
                                              comment="STUDENT/BATCH/ENTERPRISE")
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                           comment="internshipId/batchId/companyId")
    package_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    package_file_id: Mapped[str | None] = mapped_column(String(64))
    manifest_json: Mapped[dict | None] = mapped_column(JSON)
    included_items: Mapped[list | None] = mapped_column(JSON)
    missing_items: Mapped[list | None] = mapped_column(JSON)
    rule_version: Mapped[str | None] = mapped_column(String(64))
    metric_version: Mapped[str | None] = mapped_column(String(64))
    generated_by_name: Mapped[str | None] = mapped_column(String(100))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="READY",
                                        comment="READY/FAILED")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
