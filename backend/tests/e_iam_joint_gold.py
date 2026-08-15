"""E×IAM joint Gold negative matrix.

This file is intentionally NOT named ``test_*.py``. Repository-wide pytest discovery on the
Control Plane branch must not import E-series modules before PR #132 is temporarily merged.
The dedicated CI gate runs this file explicitly after a local-only merge of the exact PR #132
HEAD into the exact PR #133 HEAD.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

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


def test_same_school_cross_college_scope_is_denied(db_mode):
    """An ALLOW for one college must never bleed into a sibling college in the same tenant."""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass
    from app.services import scope_policy_service as scope_svc

    tenant_id = 1000000000000000001
    suffix = uuid4().hex[:8]
    db = get_sessionmaker()()
    try:
        college_a = College(tenant_id=tenant_id, college_name=f"E-IAM-A-{suffix}", status="ACTIVE")
        college_b = College(tenant_id=tenant_id, college_name=f"E-IAM-B-{suffix}", status="ACTIVE")
        db.add_all([college_a, college_b])
        db.flush()
        major_a = Major(tenant_id=tenant_id, college_id=college_a.id, major_name=f"A-{suffix}", status="ACTIVE")
        major_b = Major(tenant_id=tenant_id, college_id=college_b.id, major_name=f"B-{suffix}", status="ACTIVE")
        db.add_all([major_a, major_b])
        db.flush()
        class_a = SchoolClass(
            tenant_id=tenant_id,
            major_id=major_a.id,
            class_name=f"A班-{suffix}",
            grade="2026",
            status="ACTIVE",
        )
        class_b = SchoolClass(
            tenant_id=tenant_id,
            major_id=major_b.id,
            class_name=f"B班-{suffix}",
            grade="2026",
            status="ACTIVE",
        )
        db.add_all([class_a, class_b])
        db.commit()
        college_a_id = int(college_a.id)
        class_a_id = int(class_a.id)
        class_b_id = int(class_b.id)
    finally:
        db.close()

    role = "E_IAM_JOINT_COLLEGE_OPERATOR"
    scope_svc.set_policy(
        role,
        effect="ALLOW",
        target_type="COLLEGE",
        target_id=str(college_a_id),
        include_children=True,
        reason="仅允许本学院",
        tenant_id=tenant_id,
    )
    mine = scope_svc.decide(role, target_type="CLASS", target_id=str(class_a_id), tenant_id=tenant_id)
    sibling = scope_svc.decide(role, target_type="CLASS", target_id=str(class_b_id), tenant_id=tenant_id)
    assert mine["decision"] == "ALLOW"
    assert mine["reasonCode"] == "INHERITED_ALLOW"
    assert sibling["decision"] == "DENY"
    assert sibling["reasonCode"] == "DEFAULT_DENY"


def test_same_school_cross_major_scope_is_denied(db_mode):
    """An ALLOW for one major must not bleed into a sibling major under the same college."""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass
    from app.services import scope_policy_service as scope_svc

    tenant_id = 1000000000000000001
    suffix = uuid4().hex[:8]
    db = get_sessionmaker()()
    try:
        college = College(tenant_id=tenant_id, college_name=f"E-IAM-DEPT-{suffix}", status="ACTIVE")
        db.add(college)
        db.flush()
        major_a = Major(tenant_id=tenant_id, college_id=college.id, major_name=f"Dept-A-{suffix}", status="ACTIVE")
        major_b = Major(tenant_id=tenant_id, college_id=college.id, major_name=f"Dept-B-{suffix}", status="ACTIVE")
        db.add_all([major_a, major_b])
        db.flush()
        class_a = SchoolClass(
            tenant_id=tenant_id,
            major_id=major_a.id,
            class_name=f"Dept-A班-{suffix}",
            grade="2026",
            status="ACTIVE",
        )
        class_b = SchoolClass(
            tenant_id=tenant_id,
            major_id=major_b.id,
            class_name=f"Dept-B班-{suffix}",
            grade="2026",
            status="ACTIVE",
        )
        db.add_all([class_a, class_b])
        db.commit()
        major_a_id = int(major_a.id)
        class_a_id = int(class_a.id)
        class_b_id = int(class_b.id)
    finally:
        db.close()

    role = "E_IAM_JOINT_MAJOR_OPERATOR"
    scope_svc.set_policy(
        role,
        effect="ALLOW",
        target_type="MAJOR",
        target_id=str(major_a_id),
        include_children=True,
        reason="仅允许本专业组织单元",
        tenant_id=tenant_id,
    )
    mine = scope_svc.decide(role, target_type="CLASS", target_id=str(class_a_id), tenant_id=tenant_id)
    sibling = scope_svc.decide(role, target_type="CLASS", target_id=str(class_b_id), tenant_id=tenant_id)
    assert mine["decision"] == "ALLOW"
    assert mine["reasonCode"] == "INHERITED_ALLOW"
    assert sibling["decision"] == "DENY"
    assert sibling["reasonCode"] == "DEFAULT_DENY"


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


def test_expired_enterprise_hr_grant_fails_closed_in_real_mysql(db_mode):
    """An ACTIVE persisted HR grant is still denied once its validity window has expired."""
    from app.db.session import get_sessionmaker
    from app.models.internship_enterprise_portal import (
        InternshipEnterpriseAccessGrant,
        InternshipEnterpriseMember,
    )
    from app.modules.internship.services import internship_enterprise_access_service as access_svc

    now = datetime.utcnow()
    tenant_id = 8_100_000_000 + (uuid4().int % 500_000_000)
    company_id = 8_700_000_000 + (uuid4().int % 100_000_000)
    user_id = 8_800_000_000 + (uuid4().int % 100_000_000)
    campaign_id = 8_900_000_000 + (uuid4().int % 50_000_000)
    batch_id = 8_950_000_000 + (uuid4().int % 40_000_000)

    db = get_sessionmaker()()
    try:
        member = InternshipEnterpriseMember(
            tenant_id=tenant_id,
            company_id=company_id,
            user_id=user_id,
            member_role="HR",
            status="ACTIVE",
            is_primary=False,
            accepted_at=now - timedelta(days=10),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            is_deleted=False,
            version=0,
        )
        db.add(member)
        db.flush()
        grant = InternshipEnterpriseAccessGrant(
            tenant_id=tenant_id,
            member_id=member.id,
            company_id=company_id,
            grant_type="RECRUITMENT",
            campaign_id=campaign_id,
            batch_id=batch_id,
            valid_from=now - timedelta(days=2),
            valid_until=now - timedelta(seconds=1),
            status="ACTIVE",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
            is_deleted=False,
            version=0,
        )
        db.add(grant)
        db.commit()
        member_id = int(member.id)
        grant_id = int(grant.id)
    finally:
        db.close()

    db = get_sessionmaker()()
    try:
        stored = db.get(InternshipEnterpriseAccessGrant, grant_id)
        assert stored is not None
        assert stored.status == "ACTIVE"
        assert access_svc.effective_grant_status(stored, now=now) == "EXPIRED"
        with pytest.raises(AppException) as exc:
            access_svc.resolve_active_grant_in_tx(
                db,
                tenant_id=tenant_id,
                member_id=member_id,
                grant_type="RECRUITMENT",
                campaign_id=campaign_id,
                batch_id=batch_id,
                now=now,
            )
        _assert_code(exc, "NO_PERMISSION")
    finally:
        db.close()


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
