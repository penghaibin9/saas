"""Regression locks for the seven P1 production closures.

These tests focus on the security boundaries discovered during pre-merge review rather
than page cosmetics: identity type separation, final-admin protection, future-grant
fail-closed behavior, legacy duplicate authority, profile field safety, delegated
customer-success authority, serializable identity writes, signed org preview receipts,
and deterministic route replacement declarations.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.core.exceptions import AppException
from app.services import role_assignment_p1_guard_service as guard
from app.services import role_assignment_service as ras

TENANT_ID = 991_890_001


def _session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


def _tenant():
    from app.models import Tenant
    with _session() as db:
        row = db.get(Tenant, TENANT_ID)
        if row is None:
            row = Tenant(
                id=TENANT_ID,
                tenant_code="p1-review-school",
                school_name="P1生产复审学校",
                status="ACTIVE",
            )
            db.add(row)
            db.commit()


def _user(login: str, *, user_type: str = "TEACHER") -> int:
    from app.core.security import hash_password
    from app.models import User
    _tenant()
    with _session() as db:
        row = User(
            tenant_id=TENANT_ID,
            login_name=login,
            real_name=login,
            password_hash=hash_password("Init123456"),
            user_type=user_type,
            status="ACTIVE",
        )
        db.add(row)
        db.commit()
        return int(row.id)


def _role(code: str, *, status: str = "ACTIVE") -> int:
    from app.models import Role
    _tenant()
    with _session() as db:
        row = Role(
            tenant_id=TENANT_ID,
            role_code=code,
            role_name=code,
            role_type="CUSTOM",
            status=status,
        )
        db.add(row)
        db.commit()
        return int(row.id)


def _actor() -> dict:
    return {
        "userId": "db-900001",
        "tenantId": str(TENANT_ID),
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "TEACHER",
    }


def test_formal_role_future_schedule_fails_before_runtime_authority_is_written():
    with pytest.raises(AppException) as exc:
        guard.grant_assignment(
            1,
            "COUNSELOR",
            reason="未来排期不得提前授权",
            effective_at=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            tenant_id=TENANT_ID,
            user=_actor(),
        )
    assert "未来排期" in exc.value.message


def test_formal_role_student_staff_boundary_and_disabled_role(db_mode, monkeypatch):
    monkeypatch.setattr(ras, "_assert_role_delegation_allowed", lambda *args, **kwargs: None)
    student_id = _user("p1_student", user_type="STUDENT")
    teacher_id = _user("p1_teacher", user_type="TEACHER")
    _role("COUNSELOR")
    _role("STUDENT")
    _role("DISABLED_ROLE", status="DISABLED")

    with pytest.raises(AppException):
        guard.grant_assignment(
            student_id, "COUNSELOR", reason="禁止学生拿教师角色", tenant_id=TENANT_ID, user=_actor()
        )
    with pytest.raises(AppException):
        guard.grant_assignment(
            teacher_id, "STUDENT", reason="禁止教师拿学生角色", tenant_id=TENANT_ID, user=_actor()
        )
    with pytest.raises(AppException) as exc:
        guard.grant_assignment(
            teacher_id, "DISABLED_ROLE", reason="停用角色不能授予", tenant_id=TENANT_ID, user=_actor()
        )
    assert "停用角色" in exc.value.message


def test_formal_role_rejects_legacy_duplicate_runtime_authority(db_mode, monkeypatch):
    from app.models import UserRole
    monkeypatch.setattr(ras, "_assert_role_delegation_allowed", lambda *args, **kwargs: None)
    user_id = _user("p1_legacy_duplicate")
    role_id = _role("COUNSELOR_LEGACY")
    with _session() as db:
        db.add(UserRole(
            tenant_id=TENANT_ID,
            user_id=user_id,
            role_id=role_id,
            status="ACTIVE",
        ))
        db.commit()
    with pytest.raises(AppException) as exc:
        guard.grant_assignment(
            user_id, "COUNSELOR_LEGACY", reason="不得覆盖历史有效授权", tenant_id=TENANT_ID, user=_actor()
        )
    assert exc.value.http_status == 409


def test_final_active_school_admin_cannot_be_revoked(db_mode, monkeypatch):
    monkeypatch.setattr(ras, "_assert_role_delegation_allowed", lambda *args, **kwargs: None)
    admin_id = _user("p1_last_school_admin")
    _role("SCHOOL_ADMIN")
    granted = guard.grant_assignment(
        admin_id, "SCHOOL_ADMIN", reason="唯一学校管理员授权", tenant_id=TENANT_ID, user=_actor()
    )
    with pytest.raises(AppException) as exc:
        guard.revoke_assignment(
            int(granted["assignmentId"]),
            reason="不得回收最后管理员",
            expected_version=int(granted["version"]),
            tenant_id=TENANT_ID,
            user=_actor(),
        )
    assert "最后一名" in exc.value.message


def test_tenant_profile_normalizer_requires_reason_version_and_rejects_environment():
    from app.api.v1.platform_p1_closure import _normalize_profile_patch

    with pytest.raises(AppException):
        _normalize_profile_patch({"schoolType": "VOCATIONAL", "reason": "完整原因说明"})
    with pytest.raises(AppException):
        _normalize_profile_patch({"schoolType": "VOCATIONAL", "expectedVersion": 1, "reason": "短"})
    with pytest.raises(AppException) as exc:
        _normalize_profile_patch({
            "schoolType": "VOCATIONAL",
            "environment": "demo",
            "expectedVersion": 1,
            "reason": "禁止运行环境旁路修改",
        })
    assert "环境" in exc.value.message


def test_org_preview_receipt_is_actor_bound_and_expires():
    from app.api.v1.system_p1_closure import _sign_org_preview, _verify_org_preview

    now = int(time.time())
    payload = {
        "v": 1,
        "tenantId": TENANT_ID,
        "orgType": "CLASS",
        "nodeId": 9,
        "nodeVersion": 3,
        "impact": {"affectedMajors": 0, "affectedClasses": 0, "affectedStudents": 0, "affectedAssignments": 0},
        "actor": "db-900001",
        "iat": now,
        "exp": now + 60,
    }
    token = _sign_org_preview(payload)
    checked = _verify_org_preview(
        token, user={"userId": "db-900001"}, tenant_id=TENANT_ID, org_type="CLASS", node_id=9
    )
    assert checked["nodeVersion"] == 3
    with pytest.raises(AppException):
        _verify_org_preview(
            token, user={"userId": "db-OTHER"}, tenant_id=TENANT_ID, org_type="CLASS", node_id=9
        )

    expired = {**payload, "iat": now - 120, "exp": now - 1}
    with pytest.raises(AppException) as exc:
        _verify_org_preview(
            _sign_org_preview(expired),
            user={"userId": "db-900001"}, tenant_id=TENANT_ID, org_type="CLASS", node_id=9,
        )
    assert "超过 5 分钟" in exc.value.message


def test_router_source_replaces_all_p1_authorities_without_hijacking_legacy_tenant_update():
    source = Path("app/api/v1/router.py").read_text(encoding="utf-8")
    assert '_sig("/system/context", "GET")' in source
    assert '_sig("/system/accounts/{user_id}/repair-binding", "POST")' in source
    assert '_sig("/system/accounts/{user_id}/unbind", "POST")' in source
    assert '_sig("/system/role-assignments", "POST")' in source
    assert '_sig("/system/org-nodes/{node_id}/status", "PUT")' in source
    for signature in (
        '_sig("/platform/customer-success/overview", "GET")',
        '_sig("/platform/tenants/{tenant_id}/health-score", "GET")',
        '_sig("/platform/support-tickets", "GET")',
        '_sig("/platform/support-tickets", "POST")',
        '_sig("/platform/trainings", "GET")',
        '_sig("/platform/trainings", "POST")',
        '_sig("/platform/renewal-tasks", "GET")',
        '_sig("/platform/renewal-tasks", "POST")',
    ):
        assert signature in source
    assert "identity_p1_closure_router" in source
    # The old tenant-list editor owns region/CS owner/trial expiry. P1 base-profile edits use
    # the dedicated /profile endpoint and must not hijack the legacy operational PUT.
    assert '_sig("/platform/tenants/{tenant_id}", "PUT")' not in source


def test_production_route_sources_keep_atomic_signed_and_delegated_guards():
    system_source = Path("app/api/v1/system_p1_closure.py").read_text(encoding="utf-8")
    platform_source = Path("app/api/v1/platform_p1_closure.py").read_text(encoding="utf-8")
    identity_source = Path("app/services/identity_binding_p1_guard_service.py").read_text(encoding="utf-8")
    identity_router = Path("app/api/v1/identity_p1_closure.py").read_text(encoding="utf-8")
    role_source = Path("app/services/role_assignment_p1_guard_service.py").read_text(encoding="utf-8")

    assert ".with_for_update()" in system_source
    assert "CONFIG_OVERRIDE_RESTORE_INHERITANCE" in system_source
    assert "previewToken" in system_source
    assert "hmac.compare_digest" in system_source
    assert "affectedAssignments" in system_source
    assert "expectedVersion" in system_source

    assert "environment" not in platform_source.split("_PROFILE_FIELDS =", 1)[1].split("}", 1)[0]
    assert "tenant_stmt = tenant_stmt.with_for_update()" in platform_source
    assert 'require_platform_capability("tenant.view")' in platform_source
    assert 'require_platform_capability("customerSuccess.manage")' in platform_source
    assert "canEdit" in platform_source
    assert "record_critical_in_session" in platform_source
    assert '"RENEWED": set()' in platform_source
    assert '"CHURNED": set()' in platform_source
    assert '"CLOSED": set()' in platform_source

    assert "_account_for_update" in identity_source
    assert "_active_link_for_update" in identity_source
    assert "StudentProfile.id == int(student_id)" in identity_source
    assert identity_source.count("with_for_update()") >= 3
    assert identity_source.count("record_critical_in_session") >= 2
    assert "db.commit()" in identity_source
    assert "expectedVersion" in identity_router
    assert "identity_binding_p1_guard_service" in identity_router

    assert "未来排期" in role_source
    assert "学生账号固定绑定 STUDENT" in role_source
    assert "最后一名启用中的学校管理员" in role_source
    assert "_active_role_link_for" in role_source


def test_customer_success_authority_is_the_platform_workforce_canonical_capability():
    legacy = Path("app/modules/platform/services/platform_access_governance_legacy.py").read_text(encoding="utf-8")
    platform_source = Path("app/api/v1/platform_p1_closure.py").read_text(encoding="utf-8")

    assert '"PLATFORM_CUSTOMER_SUCCESS"' in legacy
    assert '"customerSuccess.manage"' in legacy
    assert platform_source.count('require_platform_capability("customerSuccess.manage")') >= 10
    assert "require_platform_super_admin" not in platform_source
