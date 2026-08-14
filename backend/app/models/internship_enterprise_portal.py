"""岗位实习 E 系列 · 企业协同 Authority 模型。

A01 按冻结顺序逐步补齐本文件。企业主档、岗位、正式志愿和最终落岗继续复用
EmpCompany / InternshipPosition / InternshipApplication / assign_position_in_tx()。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin
from app.modules.internship.enterprise_collaboration_contract import (
    CAMPAIGN_ENTERPRISE_INVITE_SOURCES,
    CAMPAIGN_ENTERPRISE_STATUSES,
    ENTERPRISE_GRANT_STATUSES,
    ENTERPRISE_GRANT_TYPES,
    ENTERPRISE_MEMBER_ROLES,
    ENTERPRISE_MEMBER_STATUSES,
    RECRUITMENT_CAMPAIGN_STATUSES,
)


class InternshipRecruitmentCampaign(PKMixin, TenantMixin, CommonMixin, Base):
    """学校招聘季 Authority；phase/材料 READY 均不持久化，按 status/windows/policy 派生。"""

    __tablename__ = "t_internship_recruitment_campaign"
    __table_args__ = (
        UniqueConstraint("tenant_id", "campaign_code", name="uk_intern_recruit_campaign_code"),
        UniqueConstraint("tenant_id", "batch_id", "round_no", name="uk_intern_recruit_campaign_round"),
        Index("ix_intern_recruit_campaign_batch_status", "tenant_id", "batch_id", "status", "is_deleted"),
        Index("ix_intern_recruit_campaign_select_window", "tenant_id", "status", "student_select_start_at", "student_select_end_at"),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_batch.id")
    campaign_code: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(200), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", comment="/".join(RECRUITMENT_CAMPAIGN_STATUSES))

    invite_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    invite_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    position_submit_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    position_submit_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    student_select_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    student_select_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_decision_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_decision_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    school_confirm_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    school_confirm_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_access_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_confirm_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    application_material_policy_json: Mapped[dict | None] = mapped_column(JSON)
    teacher_confirm_sla_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=48,
        comment="企业 ACCEPT_INTENT 后学校确认 SLA；冻结范围 1-168 小时",
    )
    remark: Mapped[str | None] = mapped_column(String(500))


class InternshipCampaignEnterprise(PKMixin, TenantMixin, CommonMixin, Base):
    """招聘季企业参与事实；不复制 EmpCompany 资质/黑名单/合作状态/准入有效期。"""

    __tablename__ = "t_internship_campaign_enterprise"
    __table_args__ = (
        UniqueConstraint("tenant_id", "campaign_id", "company_id", name="uk_intern_campaign_enterprise"),
        Index("ix_intern_campaign_enterprise_campaign_status", "tenant_id", "campaign_id", "status", "is_deleted"),
        Index("ix_intern_campaign_enterprise_company_status", "tenant_id", "company_id", "status", "is_deleted"),
    )

    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_recruitment_campaign.id")
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_emp_company.id")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="INVITED", comment="/".join(sorted(CAMPAIGN_ENTERPRISE_STATUSES)))
    invite_source: Mapped[str] = mapped_column(String(30), nullable=False, default="MANUAL", comment="/".join(sorted(CAMPAIGN_ENTERPRISE_INVITE_SOURCES)))
    invited_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoke_reason: Mapped[str | None] = mapped_column(String(500))


class InternshipEnterpriseMember(PKMixin, TenantMixin, CommonMixin, Base):
    """tenant-scoped t_user 与 canonical EmpCompany 的永久成员关系。"""

    __tablename__ = "t_internship_enterprise_member"
    __table_args__ = (
        UniqueConstraint("tenant_id", "company_id", "user_id", name="uk_intern_enterprise_member"),
        Index("ix_intern_enterprise_member_user_status", "tenant_id", "user_id", "status", "is_deleted"),
        Index("ix_intern_enterprise_member_company_status", "tenant_id", "company_id", "status", "is_deleted"),
    )

    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_emp_company.id")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_user.id")
    contact_id: Mapped[int | None] = mapped_column(BigInteger, comment="可对齐 t_internship_enterprise_contact.id")
    member_role: Mapped[str] = mapped_column(String(30), nullable=False, comment="/".join(sorted(ENTERPRISE_MEMBER_ROLES)))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="INVITED", comment="/".join(sorted(ENTERPRISE_MEMBER_STATUSES)))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invited_phone_hash: Mapped[str | None] = mapped_column(String(128))
    invite_token_hash: Mapped[str | None] = mapped_column(String(128))
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipEnterpriseAccessGrant(PKMixin, TenantMixin, CommonMixin, Base):
    """企业成员的时效访问授权；招聘权与实习期协同权严格分离。"""

    __tablename__ = "t_internship_enterprise_access_grant"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "member_id", "grant_type", "campaign_id", "batch_id",
            name="uk_intern_enterprise_access_grant",
        ),
        Index("ix_intern_enterprise_grant_member_validity", "tenant_id", "member_id", "status", "valid_until"),
        Index("ix_intern_enterprise_grant_company_validity", "tenant_id", "company_id", "status", "valid_until"),
    )

    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_internship_enterprise_member.id")
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_emp_company.id")
    grant_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="/".join(sorted(ENTERPRISE_GRANT_TYPES)))
    campaign_id: Mapped[int | None] = mapped_column(BigInteger, comment="RECRUITMENT grant → t_internship_recruitment_campaign.id")
    batch_id: Mapped[int | None] = mapped_column(BigInteger, comment="招聘/实习协同所属 t_internship_batch.id")
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", comment="/".join(sorted(ENTERPRISE_GRANT_STATUSES)))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    revoke_reason: Mapped[str | None] = mapped_column(String(500))


# Register later E-series additive models in Base.metadata whenever app.models imports this module.
from app.models.internship_student_profile import (  # noqa: E402,F401
    StudentInternshipProfile,
    StudentInternshipProfileItem,
)
from app.models.internship_application_material_snapshot import (  # noqa: E402,F401
    InternshipApplicationMaterialSnapshot,
)
from app.models.internship_volunteer_group import InternshipVolunteerGroup  # noqa: E402,F401
