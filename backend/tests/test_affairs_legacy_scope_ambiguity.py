"""旧名称范围必须唯一定位，不因同名或删后重建扩权。"""
from datetime import datetime, timedelta

import pytest

from test_affairs_security import TID, _base


@pytest.fixture(autouse=True)
def tenant_context(db_mode):
    from app.core.context import get_tenant, set_tenant
    previous = get_tenant()
    set_tenant(TID)
    yield
    set_tenant(previous)


def _actor(db, role_code, scope_type, value):
    from affairs_contract_test_support import _ensure_role_user
    from app.models import TeacherStudentScope
    account = _ensure_role_user(db, role_code, "legacy_ambiguous_owner", "旧范围验收人")
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key=account.login_name,
        role_code=role_code, scope_type=scope_type, ref_value=value, status="ACTIVE"))
    db.flush()
    return account, {"userId": str(account.id), "loginName": account.login_name,
        "tenantId": str(TID), "currentRoleCode": role_code, "userType": "TEACHER"}


def _formal(db, account, role_code, scope_type, scope_id):
    from sqlalchemy import select
    from app.models import Role, RoleAssignmentScope, UserRole
    member = db.scalar(select(UserRole).join(Role, Role.id == UserRole.role_id).where(
        UserRole.tenant_id == TID, UserRole.user_id == account.id, Role.role_code == role_code))
    db.add(RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=member.id,
        role_code=role_code, scope_type=scope_type, scope_id=scope_id, status="ACTIVE",
        effective_at=datetime.utcnow() - timedelta(days=1)))
    db.flush()


@pytest.mark.parametrize("collision", ["same", "suffix", "deleted_reuse"])
def test_legacy_class_name_never_expands_to_another_college(db_mode, collision):
    from app.core.affairs_security import build_affairs_context
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    ids = _base(db_mode, counselor_scope=False, college_scope=False)
    with get_sessionmaker()() as db:
        first, other = db.get(SchoolClass, ids["cA"]), db.get(SchoolClass, ids["cC"])
        first.class_name = "旧范围验收班"
        account, user = _actor(db, "COUNSELOR", "CLASS", first.class_name)
        assert build_affairs_context(user, db).class_ids == {first.id}
        other.class_name = "旧范围验收" if collision == "suffix" else first.class_name
        first.is_deleted = collision == "deleted_reuse"
        db.flush()
        assert build_affairs_context(user, db).class_ids == set()
        target = other if collision == "deleted_reuse" else first
        _formal(db, account, "COUNSELOR", "CLASS", target.id)
        assert build_affairs_context(user, db).class_ids == {target.id}


def test_legacy_college_ambiguity_is_rejected_by_claims_scope_and_assignees(db_mode):
    from app.core.affairs_security import build_affairs_context
    from app.db.session import get_sessionmaker
    from app.models import College
    from app.services.auth_service_db import _inject_org_scope_claims
    from app.services.affairs_assignee_service import resolve_assignee_ids
    ids = _base(db_mode, counselor_scope=False, college_scope=False)
    with get_sessionmaker()() as db:
        first, other = db.get(College, ids["col1"]), db.get(College, ids["col2"])
        account, user = _actor(db, "COLLEGE_ADMIN", "COLLEGE", first.college_name)
        assert build_affairs_context(user, db).college_ids == {first.id}
        assert resolve_assignee_ids(db, "COLLEGE_REVIEW", student_id=ids["A"]) == [account.id]
        other.college_name = first.college_name
        db.flush()
        assert build_affairs_context(user, db).college_ids == set()
        claims = dict(user)
        _inject_org_scope_claims(db, account, claims)
        assert "collegeIds" not in claims
        for student_id in (ids["A"], ids["C"]):
            assert resolve_assignee_ids(db, "COLLEGE_REVIEW", student_id=student_id) == []
        _formal(db, account, "COLLEGE_ADMIN", "COLLEGE", first.id)
        assert build_affairs_context(user, db).college_ids == {first.id}
        claims = dict(user)
        _inject_org_scope_claims(db, account, claims)
        assert claims["collegeIds"] == [str(first.id)]
        assert resolve_assignee_ids(db, "COLLEGE_REVIEW", student_id=ids["A"]) == [account.id]
        assert resolve_assignee_ids(db, "COLLEGE_REVIEW", student_id=ids["C"]) == []


def test_legacy_major_claims_use_database_name_equality_and_reject_reuse(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Major, SchoolClass
    from app.services.auth_service_db import _inject_org_scope_claims
    ids = _base(db_mode, counselor_scope=False, college_scope=False)
    with get_sessionmaker()() as db:
        first = db.get(Major, db.get(SchoolClass, ids["cA"]).major_id)
        other = db.get(Major, db.get(SchoolClass, ids["cC"]).major_id)
        first.major_name = "LegacyMajor"
        account, user = _actor(db, "GD_MAJOR_ADMIN", "MAJOR", first.major_name)
        claims = dict(user)
        _inject_org_scope_claims(db, account, claims)
        assert claims["majorIds"] == [str(first.id)]
        other.major_name = "legacymajor"
        db.flush()
        for deleted in (False, True):
            first.is_deleted = deleted
            db.flush()
            claims = dict(user)
            _inject_org_scope_claims(db, account, claims)
            assert "majorIds" not in claims and "collegeIds" not in claims


def test_real_login_directory_and_mobile_share_ambiguous_legacy_scope(client, db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, User
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    ids = _base(db_mode, counselor_scope=False, college_scope=False)
    with get_sessionmaker()() as db:
        first, other = db.get(SchoolClass, ids["cA"]), db.get(SchoolClass, ids["cC"])
        other.class_name = first.class_name
        account, _ = _actor(db, "COUNSELOR", "CLASS", first.class_name)
        account.password_hash = hash_password(TEST_LOGIN_PASSWORD)
        account.must_change_password = False
        uid = account.id
        db.commit()

    for formal in (False, True):
        if formal:
            with get_sessionmaker()() as db:
                _formal(db, db.get(User, uid), "COUNSELOR", "CLASS", ids["cA"])
                db.commit()
        headers = _real_hdr(client, "legacy_ambiguous_owner", client_type="TEACHER_MINI")
        for route in ("/api/v1/students", "/api/v1/teacher-mobile/students"):
            response = client.get(route, headers=headers)
            assert response.status_code == 200, response.text
            items = response.json()["data"]["items"]
            assert {row["studentNo"] for row in items} == ({"A001"} if formal else set())
        for sid, allowed in ((ids["A"], formal), (ids["C"], False)):
            for route in (f"/api/v1/students/{sid}", f"/api/v1/teacher-mobile/students/{sid}/projection"):
                response = client.get(route, headers=headers)
                assert response.status_code == 200 if allowed else response.status_code in (403, 404), response.text
