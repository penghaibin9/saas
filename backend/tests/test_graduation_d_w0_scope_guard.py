"""D-W0 Graduation read data-scope contract.

Permission grants and organization data scope are independent authorities. Tenant-defined
roles with graduation.view must never inherit tenant-wide visibility merely because their
role code is unknown to the Graduation service.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard

TID = 1000000000000000001


def _ctx(scope_type, college_ids=()):
    return SimpleNamespace(scope_type=scope_type, college_ids=set(college_ids))


def test_tenant_all_scope_stays_unrestricted(monkeypatch):
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: _ctx("TENANT_ALL"))
    assert guard.graduation_college_scope_ids(object(), {"currentRoleCode": "ACADEMIC_ADMIN"}) is None


def test_custom_college_scope_uses_shared_context(monkeypatch):
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: _ctx("COLLEGE", {21, 22}))
    assert guard.graduation_college_scope_ids(object(), {"currentRoleCode": "CUSTOM_GRAD_VIEW"}) == {21, 22}


@pytest.mark.parametrize("scope_type", ["NONE", "CLASS", "STUDENT", "SELF", "DORM_BUILDING"])
def test_non_college_custom_scope_never_falls_back_to_tenant_all(monkeypatch, scope_type):
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: _ctx(scope_type, {99}))
    assert guard.graduation_college_scope_ids(object(), {"currentRoleCode": "CUSTOM_GRAD_VIEW"}) == set()


def test_public_graduation_router_installs_scope_guard():
    from app.modules.academic_affairs.routers import graduation_core_router

    installed = graduation_core_router.grad_svc._college_scope_ids
    assert getattr(installed, "_graduation_scope_guard", False) is True


@pytest.mark.usefixtures("db_mode")
def test_custom_college_scope_resolves_real_teacher_scope_row():
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import College, TeacherStudentScope

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        college = College(
            tenant_id=TID,
            college_name="D-W0自定义毕业审核范围学院",
            code="DW0-GRAD-SCOPE-COL",
            status="ACTIVE",
        )
        db.add(college)
        db.flush()
        db.add(TeacherStudentScope(
            tenant_id=TID,
            teacher_key="dw0_custom_grad_view",
            teacher_name="自定义毕业审核员",
            role_code="CUSTOM_GRAD_VIEW",
            scope_type="COLLEGE",
            ref_value=college.college_name,
            status="ACTIVE",
        ))
        db.commit()

        scoped_user = {
            "loginName": "dw0_custom_grad_view",
            "realName": "自定义毕业审核员",
            "userType": "TEACHER",
            "currentRoleCode": "CUSTOM_GRAD_VIEW",
            "tenantId": str(TID),
        }
        assert guard.graduation_college_scope_ids(db, scoped_user) == {int(college.id)}

        no_scope_user = {
            "loginName": "dw0_custom_grad_no_scope",
            "realName": "未配置范围审核员",
            "userType": "TEACHER",
            "currentRoleCode": "CUSTOM_GRAD_VIEW",
            "tenantId": str(TID),
        }
        assert guard.graduation_college_scope_ids(db, no_scope_user) == set()
    finally:
        db.close()
        set_tenant(None)
