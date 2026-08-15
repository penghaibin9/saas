"""E-A01 / A01-1: freeze E1 authority contracts before persistence work."""
from __future__ import annotations

import inspect

from app.modules.internship import enterprise_collaboration_contract as contract
from app.modules.internship.services import internship_application_service


def test_canonical_authorities_remain_the_existing_internship_chain():
    assert contract.CANONICAL_AUTHORITIES == {
        "company": "EmpCompany",
        "position": "InternshipPosition",
        "application": "InternshipApplication",
        "placement_command": "assign_position_in_tx",
        "internship_record": "InternshipRecord",
        "login_user": "User",
    }
    assert {
        "EnterpriseCompany",
        "EnterpriseJob",
        "EnterpriseUser",
        "StudentVolunteer",
        "PlacementResult",
        "RecruitmentApplication",
    } <= contract.FORBIDDEN_DUPLICATE_AUTHORITIES

    review_source = inspect.getsource(internship_application_service.review_application)
    assert "student_svc.assign_position_in_tx(" in review_source


def test_campaign_lifecycle_and_windows_are_frozen_without_persisted_phase():
    assert contract.RECRUITMENT_CAMPAIGN_STATUSES == (
        "DRAFT",
        "OPEN",
        "FROZEN",
        "CLOSED",
        "ARCHIVED",
    )
    assert contract.RECRUITMENT_CAMPAIGN_TRANSITIONS == {
        "DRAFT": frozenset({"OPEN"}),
        "OPEN": frozenset({"FROZEN", "CLOSED"}),
        "FROZEN": frozenset({"CLOSED"}),
        "CLOSED": frozenset({"ARCHIVED"}),
        "ARCHIVED": frozenset(),
    }
    assert "phase" not in contract.RECRUITMENT_CAMPAIGN_PERSISTED_FIELDS
    assert set(contract.RECRUITMENT_CAMPAIGN_WINDOW_FIELDS) == {
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
    }


def test_campaign_enterprise_only_owns_participation_not_company_qualification():
    assert contract.CAMPAIGN_ENTERPRISE_STATUSES == frozenset(
        {"INVITED", "ACCEPTED", "DECLINED", "SUSPENDED", "REVOKED"}
    )
    assert contract.CAMPAIGN_ENTERPRISE_TRANSITIONS["SUSPENDED"] == frozenset(
        {"ACCEPTED", "REVOKED"}
    )
    assert contract.CAMPAIGN_ENTERPRISE_INVITE_SOURCES == frozenset(
        {"MANUAL", "REUSE", "PUBLIC_REQUEST"}
    )
    assert contract.CAMPAIGN_ENTERPRISE_FORBIDDEN_COPIES == frozenset(
        {"qualification_status", "blacklist", "coop_status", "access_valid_until"}
    )


def test_enterprise_member_reuses_t_user_roles_and_has_no_second_login_authority():
    assert contract.CANONICAL_AUTHORITIES["login_user"] == "User"
    assert "EnterpriseUser" in contract.FORBIDDEN_DUPLICATE_AUTHORITIES
    assert contract.ENTERPRISE_MEMBER_ROLES == frozenset(
        {"COMPANY_ADMIN", "HR", "MENTOR"}
    )
    assert contract.ENTERPRISE_MEMBER_STATUSES == frozenset(
        {"INVITED", "ACTIVE", "DISABLED"}
    )


def test_access_grant_contract_separates_recruitment_from_internship_collaboration():
    assert contract.ENTERPRISE_GRANT_TYPES == frozenset(
        {"RECRUITMENT", "INTERNSHIP_COLLAB"}
    )
    assert contract.ENTERPRISE_GRANT_STATUSES == frozenset(
        {"ACTIVE", "REVOKED", "EXPIRED"}
    )


def test_enterprise_context_is_server_derived_and_fail_closed():
    assert contract.ENTERPRISE_CONTEXT_GUARD_CHAIN == (
        "user_active",
        "member_active",
        "tenant_match",
        "company_scope",
        "grant_active_not_expired",
        "campaign_enterprise_accepted",
        "resource_owned_by_company",
    )
    assert contract.ENTERPRISE_CONTEXT_CLIENT_AUTHORITY_FIELDS == frozenset(
        {"companyId", "company_id"}
    )
