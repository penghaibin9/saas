"""E-A01 / A01-6 enterprise invite, activation and context contracts."""
from __future__ import annotations

import inspect

from app.api.v1 import route_registration
from app.modules.internship.dependencies import enterprise_context
from app.modules.internship.routers import internship_enterprise_portal
from app.modules.internship.schemas.internship_recruitment_campaign import (
    CampaignEnterpriseInvite,
    EnterpriseInviteAccept,
    EnterpriseLogin,
)
from app.modules.internship.services import internship_enterprise_auth_service as auth_svc


def test_invite_token_uses_random_secret_platform_hmac_and_hash_only_persistence():
    issue_source = inspect.getsource(auth_svc.issue_company_invite)
    hash_source = inspect.getsource(auth_svc._invite_hash)
    assert "secrets.token_urlsafe(32)" in issue_source
    assert 'hash_sensitive(token, "internship_enterprise_invite")' in hash_source
    assert "member.invite_token_hash = _invite_hash(raw)" in issue_source
    assert "inviteToken" in issue_source
    assert "expires_at = _invite_expiry(campaign, now)" in issue_source
    assert "member.invite_expires_at = expires_at" in issue_source
    assert "md5" not in issue_source.lower()


def test_invite_issue_and_accept_share_fail_closed_invite_window():
    guard_source = inspect.getsource(auth_svc._assert_invite_window)
    expiry_source = inspect.getsource(auth_svc._invite_expiry)
    issue_source = inspect.getsource(auth_svc.issue_company_invite)
    load_source = inspect.getsource(auth_svc._load_invite_in_tx)
    assert 'assert_campaign_operation_window(campaign, "INVITE", now=now)' in guard_source
    assert "campaign.enterprise_access_end_at" in guard_source
    assert "min(now + _INVITE_TTL, campaign.invite_end_at, campaign.enterprise_access_end_at)" in expiry_source
    assert "_invite_expiry(campaign, now)" in issue_source
    assert "_assert_invite_window(campaign, current, public_token=True)" in load_source
    assert "member.invite_expires_at <= current" in load_source


def test_invite_accept_requires_phone_match_is_single_use_and_activates_one_transaction():
    source = inspect.getsource(auth_svc.accept_invite)
    load_source = inspect.getsource(auth_svc._load_invite_in_tx)
    assert "phone_hash = hash_sensitive" in source
    assert "phone_hash != member.invited_phone_hash" in source
    assert "lock=True" in source
    assert 'member.status = "ACTIVE"' in source
    assert 'participation.status = "ACCEPTED"' in source
    assert "member.invite_token_hash = None" in source
    assert "member.invite_expires_at = None" in source
    assert "access_svc.issue_grant_in_tx(" in source
    assert "db.commit()" in source
    assert 'member.status != "INVITED"' in load_source
    assert "member.invite_expires_at <= current" in load_source


def test_invite_reuses_t_user_and_never_creates_enterprise_user_authority():
    source = inspect.getsource(auth_svc._ensure_invited_user_in_tx)
    assert "select(User)" in source
    assert 'user.user_type or ""' in source
    assert 'user_type="ENTERPRISE_MENTOR"' in source
    assert 'status="DISABLED"' in source
    assert "hash_password(secrets.token_urlsafe(48))" in source
    assert "EnterpriseUser" not in source


def test_enterprise_login_requires_school_context_server_member_and_company_admission():
    fields = EnterpriseLogin.model_fields
    assert set(fields) == {"tenantCode", "loginName", "password", "memberId"}
    assert "companyId" not in fields
    source = inspect.getsource(auth_svc.login)
    admission_source = inspect.getsource(auth_svc._require_company_admission_for_auth)
    assert "_tenant_by_code(" in source
    assert 'User.user_type == "ENTERPRISE_MENTOR"' in source
    assert 'User.status == "ACTIVE"' in source
    assert "_active_members(" in source
    assert "ENTERPRISE_CONTEXT_REQUIRED" in source
    assert "_require_company_admission_for_auth(" in source
    assert "company_id=member.company_id" in source
    assert "_get_company(" in admission_source
    assert "require_admission=True" in admission_source
    assert 'AppException(\n            "NO_PERMISSION"' in admission_source


def test_access_and_refresh_revalidate_company_admission_before_token_renewal():
    validate_source = inspect.getsource(auth_svc.validate_enterprise_claims)
    refresh_source = inspect.getsource(auth_svc.refresh)
    assert "_require_company_admission_for_auth(" in validate_source
    assert "company_id=member.company_id" in validate_source
    assert "validate_enterprise_claims(claims)" in refresh_source
    assert "_token_result(" in refresh_source


def test_enterprise_context_revalidates_user_member_company_admission_grant_and_campaign():
    principal_source = inspect.getsource(enterprise_context.get_enterprise_principal)
    recruitment_source = inspect.getsource(enterprise_context.resolve_recruitment_context)
    assert "decode_and_validate_access" in principal_source
    assert "EmpCompany.id == member.company_id" in principal_source
    assert 'company.status or ""' in principal_source
    assert "company.blacklist" in principal_source
    assert 'company.coop_status != "ACTIVE"' in principal_source
    assert 'company.qualification_status != "PASSED"' in principal_source
    assert "company.access_valid_until" in principal_source
    assert "set_tenant(" in principal_source
    assert "set_current_user(" in principal_source
    assert "resolve_active_grant_in_tx(" in recruitment_source
    assert 'grant_type="RECRUITMENT"' in recruitment_source
    assert 'InternshipCampaignEnterprise.status == "ACCEPTED"' in recruitment_source
    assert "principal.company_id" in recruitment_source


def test_enterprise_router_is_mounted_outside_staff_bundle_with_explicit_auth_policy():
    register_source = inspect.getsource(route_registration.register_internship_routes)
    router_source = inspect.getsource(internship_enterprise_portal)
    assert "internship_enterprise_portal" in register_source
    assert "api_router.include_router(internship_enterprise_portal.router)" in register_source
    assert "api_router.include_router(internship_enterprise_portal.router, dependencies=d)" not in register_source
    assert "require_staff" not in router_source
    assert "require_enterprise_permission as require_permission" in router_source
    assert router_source.count('openapi_extra={"x-internship-auth": "public"}') == 4
    assert 'Depends(require_permission("internship.enterprise.view"))' in router_source
    assert 'Depends(require_permission("internship.application.view"))' in router_source
    assert 'Depends(require_permission("internship.application.review"))' in router_source


def test_enterprise_recruitment_permissions_are_role_scoped_and_fail_closed():
    source = inspect.getsource(enterprise_context.require_enterprise_permission)
    permissions = enterprise_context._ENTERPRISE_RECRUITMENT_PERMISSION_ROLES
    assert "get_enterprise_principal" in source
    assert "unregistered enterprise internship permission" in source
    assert 'AppException("NO_PERMISSION"' in source
    assert permissions["internship.enterprise.view"] == frozenset({"COMPANY_ADMIN", "HR", "MENTOR"})
    assert permissions["internship.application.view"] == frozenset({"COMPANY_ADMIN", "HR"})
    assert permissions["internship.application.review"] == frozenset({"COMPANY_ADMIN", "HR"})
    assert "MENTOR" not in permissions["internship.application.view"]
    assert "MENTOR" not in permissions["internship.application.review"]


def test_enterprise_public_auth_schemas_do_not_accept_company_scope():
    assert "companyId" not in EnterpriseInviteAccept.model_fields
    assert "companyId" not in EnterpriseLogin.model_fields
    assert "companyId" in CampaignEnterpriseInvite.model_fields
