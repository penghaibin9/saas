"""E-A01 frozen contracts for internship enterprise collaboration.

This module is deliberately DB-free. Later A01 cards import these constants instead of
re-declaring lifecycle strings or canonical ownership boundaries in services and routers.
"""
from __future__ import annotations

CANONICAL_AUTHORITIES = {
    "company": "EmpCompany",
    "position": "InternshipPosition",
    "application": "InternshipApplication",
    "placement_command": "assign_position_in_tx",
    "internship_record": "InternshipRecord",
    "login_user": "User",
}

FORBIDDEN_DUPLICATE_AUTHORITIES = frozenset(
    {
        "EnterpriseCompany",
        "EnterpriseJob",
        "EnterpriseUser",
        "InternshipRecruitmentJob",
        "StudentVolunteer",
        "PlacementResult",
        "RecruitmentApplication",
    }
)

RECRUITMENT_CAMPAIGN_STATUSES = (
    "DRAFT",
    "OPEN",
    "FROZEN",
    "CLOSED",
    "ARCHIVED",
)
RECRUITMENT_CAMPAIGN_TRANSITIONS = {
    "DRAFT": frozenset({"OPEN"}),
    "OPEN": frozenset({"FROZEN", "CLOSED"}),
    "FROZEN": frozenset({"CLOSED"}),
    "CLOSED": frozenset({"ARCHIVED"}),
    "ARCHIVED": frozenset(),
}
RECRUITMENT_CAMPAIGN_DERIVED_PHASES = frozenset(
    {
        "PREPARE",
        "INVITING",
        "POSITION_SUBMITTING",
        "STUDENT_SELECTING",
        "ENTERPRISE_DECIDING",
        "SCHOOL_CONFIRMING",
        "FROZEN",
        "CLOSED",
        "ARCHIVED",
    }
)
RECRUITMENT_CAMPAIGN_WINDOW_FIELDS = (
    "invite_start_at",
    "invite_end_at",
    "position_submit_start_at",
    "position_submit_end_at",
    "student_select_start_at",
    "student_select_end_at",
    "enterprise_decision_start_at",
    "enterprise_decision_end_at",
    "school_confirm_start_at",
    "school_confirm_end_at",
    "enterprise_access_end_at",
)
RECRUITMENT_CAMPAIGN_PERSISTED_FIELDS = frozenset(
    {
        "tenant_id",
        "batch_id",
        "campaign_code",
        "campaign_name",
        "round_no",
        "status",
        *RECRUITMENT_CAMPAIGN_WINDOW_FIELDS,
        "enterprise_confirm_required",
        "remark",
        "version",
        "created_at",
        "updated_at",
        "is_deleted",
    }
)

CAMPAIGN_ENTERPRISE_STATUSES = frozenset(
    {"INVITED", "ACCEPTED", "DECLINED", "SUSPENDED", "REVOKED"}
)
CAMPAIGN_ENTERPRISE_TRANSITIONS = {
    "INVITED": frozenset({"ACCEPTED", "DECLINED", "REVOKED"}),
    "ACCEPTED": frozenset({"SUSPENDED", "REVOKED"}),
    "SUSPENDED": frozenset({"ACCEPTED", "REVOKED"}),
    "DECLINED": frozenset(),
    "REVOKED": frozenset(),
}
CAMPAIGN_ENTERPRISE_INVITE_SOURCES = frozenset(
    {"MANUAL", "REUSE", "PUBLIC_REQUEST"}
)
CAMPAIGN_ENTERPRISE_FORBIDDEN_COPIES = frozenset(
    {"qualification_status", "blacklist", "coop_status", "access_valid_until"}
)

ENTERPRISE_MEMBER_ROLES = frozenset({"COMPANY_ADMIN", "HR", "MENTOR"})
ENTERPRISE_MEMBER_STATUSES = frozenset({"INVITED", "ACTIVE", "DISABLED"})

ENTERPRISE_GRANT_TYPES = frozenset({"RECRUITMENT", "INTERNSHIP_COLLAB"})
ENTERPRISE_GRANT_STATUSES = frozenset({"ACTIVE", "REVOKED", "EXPIRED"})

ENTERPRISE_CONTEXT_GUARD_CHAIN = (
    "user_active",
    "member_active",
    "tenant_match",
    "company_scope",
    "grant_active_not_expired",
    "campaign_enterprise_accepted",
    "resource_owned_by_company",
)
ENTERPRISE_CONTEXT_CLIENT_AUTHORITY_FIELDS = frozenset({"companyId", "company_id"})
