"""E×IAM joint Gold negative matrix.

This file is intentionally NOT named ``test_*.py``. Repository-wide pytest discovery on the
Control Plane branch must not import E-series modules before PR #132 is temporarily merged.
The dedicated CI gate runs this file explicitly after a local-only merge of the exact PR #132
HEAD into the exact PR #133 HEAD.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core import permissions
from app.core.exceptions import AppException
from app.services import module_access_service


def _assert_code(exc_info, code: str) -> None:
    assert getattr(exc_info.value, "code", None) == code, repr(exc_info.value)


def test_school_without_internship_entitlement_is_denied(monkeypatch):
    """School-side staff authorization must stop before domain permission when module is absent."""
    snapshot = {
        "traceId": "joint-gold",
        "tenantId": 991001,
        "entitledFeatures": {},
        "schoolGate": {},
        "tenantStatus": "ACTIVE",
        "tenantStateError": "",
    }
    monkeypatch.setattr(module_access_service, "_load_request_snapshot", lambda _tenant_id: snapshot)
    with pytest.raises(AppException) as exc:
        module_access_service.assert_module_access(991001, "internship", write=False)
    _assert_code(exc, "NO_PERMISSION")


def test_normal_teacher_cannot_manage_recruitment():
    """A generic academic teacher must not inherit the recruitment writer permission."""
    user = {
        "userId": "joint-normal-teacher",
        "userType": "TEACHER",
        "tenantId": "991001",
        "currentRoleCode": "ACADEMIC_TEACHER",
    }
    assert permissions.has_permission(user, "internship.recruitment.manage") is False
    with pytest.raises(AppException) as exc:
        permissions.enforce_permission(user, "internship.recruitment.manage")
    _assert_code(exc, "NO_PERMISSION")


def test_school_admin_identity_cannot_be_used_as_enterprise_principal():
    """School RBAC is never an alternate root into enterprise APIs."""
    from app.modules.internship.services import internship_enterprise_auth_service as auth_svc

    claims = {
        "userId": "db-1",
        "userType": "TEACHER",
        "tenantId": "991001",
        "currentRoleCode": "SCHOOL_ADMIN",
        "enterpriseMemberId": "1",
        "companyId": "1",
    }
    with pytest.raises(AppException) as exc:
        auth_svc.validate_enterprise_claims(claims)
    _assert_code(exc, "UNAUTHORIZED")


def test_enterprise_mentor_cannot_review_recruitment_applications():
    """MENTOR can collaborate with owned students but cannot become an HR recruitment reviewer."""
    from app.modules.internship.dependencies import enterprise_context

    principal = enterprise_context.EnterprisePrincipal(
        tenant_id=991001,
        tenant_code="joint",
        user_id=1,
        member_id=2,
        company_id=3,
        member_role="MENTOR",
        claims={},
    )
    dependency = enterprise_context.require_enterprise_permission("internship.application.review")
    with pytest.raises(AppException) as exc:
        dependency(principal=principal)
    _assert_code(exc, "NO_PERMISSION")


def test_expired_enterprise_hr_grant_fails_closed_in_canonical_resolver(monkeypatch):
    """Expiry is evaluated on every resolve; stored ACTIVE alone is never sufficient."""
    from app.models.internship_enterprise_portal import InternshipEnterpriseAccessGrant
    from app.modules.internship.services import internship_enterprise_access_service as access_svc

    now = datetime(2026, 8, 15, 12, 0, 0)
    member = SimpleNamespace(id=11, company_id=22, tenant_id=991001, status="ACTIVE")
    grant = InternshipEnterpriseAccessGrant(
        tenant_id=991001,
        member_id=11,
        company_id=22,
        grant_type="RECRUITMENT",
        campaign_id=33,
        batch_id=44,
        valid_from=now - timedelta(days=2),
        valid_until=now - timedelta(seconds=1),
        status="ACTIVE",
    )

    class _DB:
        def scalar(self, _stmt):
            return grant

    monkeypatch.setattr(access_svc, "_get_member", lambda *_args, **_kwargs: member)
    with pytest.raises(AppException) as exc:
        access_svc.resolve_active_grant_in_tx(
            _DB(),
            tenant_id=991001,
            member_id=11,
            grant_type="RECRUITMENT",
            campaign_id=33,
            batch_id=44,
            now=now,
        )
    _assert_code(exc, "NO_PERMISSION")


def test_wrong_enterprise_resource_is_denied():
    from app.modules.internship.dependencies import enterprise_context

    context = SimpleNamespace(company_id=2001)
    with pytest.raises(AppException) as exc:
        enterprise_context.assert_resource_company(context, 2002)
    _assert_code(exc, "NO_PERMISSION")


def test_mentor_scope_is_company_batch_and_bound_contact():
    """The mentor row filter must be narrower than company HR scope."""
    from app.models import InternshipRecord
    from app.modules.internship.services import internship_enterprise_collaboration_service as collab_svc

    context = SimpleNamespace(tenant_id=991001, company_id=2001, batch_id=3001)
    predicates = collab_svc._record_conditions(context, mentor_contact_id=4001)
    sql = " AND ".join(str(predicate) for predicate in predicates)
    assert "tenant_id" in sql
    assert "enterprise_id" in sql
    assert "batch_id" in sql
    assert "mentor_contact_id" in sql
    assert str(InternshipRecord.mentor_contact_id) in sql or "mentor_contact_id" in sql


def test_e_series_does_not_introduce_a_second_identity_or_school_iam_root():
    """Enterprise auth reuses t_user + member/grant/context and remains separate from school RBAC."""
    import inspect
    import app.models as models
    from app.modules.internship.dependencies import enterprise_context
    from app.modules.internship.services import internship_enterprise_auth_service as auth_svc
    from app.modules.internship.services import internship_enterprise_member_service as member_svc

    assert not hasattr(models, "EnterpriseUser")
    auth_source = inspect.getsource(auth_svc)
    member_source = inspect.getsource(member_svc)
    context_source = inspect.getsource(enterprise_context)
    assert "from app.models import EmpCompany, Tenant, User" in auth_source
    assert "select(User)" in auth_source
    assert "InternshipEnterpriseMember" in auth_source
    assert "EnterpriseUser" not in auth_source
    assert "User" in member_source and "InternshipEnterpriseMember" in member_source
    assert "decode_and_validate_access" in context_source
    assert "resolve_active_grant_in_tx" in context_source
    assert "require_staff" not in context_source
    assert all(code.startswith("internship.") for code in enterprise_context._ENTERPRISE_RECRUITMENT_PERMISSION_ROLES)
