"""P1-03 / AA-005 targeted MySQL regression for program two-level review Authority."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_program_service as svc

TID = 1000000000000000805
COLLEGE_USER = {
    "userId": "aa-r3-program-college-a",
    "loginName": "aa-r3-program-college-a",
    "userType": "TEACHER",
    "currentRoleCode": "V5_PROGRAM_COLLEGE_REVIEWER",
}
SCHOOL_USER = {
    "userId": "aa-r3-program-school",
    "loginName": "aa-r3-program-school",
    "userType": "TEACHER",
    "currentRoleCode": "V5_PROGRAM_SCHOOL_REVIEWER",
}


@pytest.fixture(autouse=True)
def _program_tenant_context():
    from app.core.context import get_tenant, set_tenant
    previous = get_tenant()
    set_tenant(TID)
    try:
        yield
    finally:
        set_tenant(previous)


def _seed_review_identities(db, college_id):
    from app.models import Role, RoleAssignmentScope, RolePermission, StaffAssignment, User, UserRole
    from tests.support_academic_review_identity import _ensure_permission

    for claim, scope_type, scope_id, assignment in (
        (COLLEGE_USER, "COLLEGE", college_id, "SECRETARY"),
        (SCHOOL_USER, "SCHOOL", 0, "ACADEMIC_REVIEWER"),
    ):
        user = db.scalar(select(User).where(User.tenant_id == TID, User.login_name == claim["loginName"]))
        if user is None:
            user = User(tenant_id=TID, login_name=claim["loginName"], real_name=claim["loginName"],
                user_type="TEACHER", password_hash="unused-in-service-test", status="ACTIVE")
            db.add(user); db.flush()
        role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == claim["currentRoleCode"]))
        if role is None:
            role = Role(tenant_id=TID, role_code=claim["currentRoleCode"], role_name="培养方案审核测试岗位",
                role_type="CUSTOM", status="ACTIVE")
            db.add(role); db.flush()
        link = db.scalar(select(UserRole).where(UserRole.tenant_id == TID, UserRole.user_id == user.id, UserRole.role_id == role.id))
        if link is None:
            link = UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE")
            db.add(link); db.flush()
        for code in ("academicAffairs.program.view", "academicAffairs.program.manage", "academicAffairs.program.review"):
            permission = _ensure_permission(db, code)
            if not db.scalar(select(RolePermission.id).where(RolePermission.tenant_id == TID,
                    RolePermission.role_id == role.id, RolePermission.permission_id == permission.id)):
                db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
        if not db.scalar(select(RoleAssignmentScope.id).where(RoleAssignmentScope.tenant_id == TID,
                RoleAssignmentScope.user_role_id == link.id, RoleAssignmentScope.scope_type == scope_type,
                RoleAssignmentScope.scope_id == scope_id)):
            db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=user.id,
                role_code=role.role_code, scope_type=scope_type, scope_id=scope_id, status="ACTIVE",
                effective_at=datetime(2020, 1, 1)))
        org_id = TID if scope_type == "SCHOOL" else college_id
        if not db.scalar(select(StaffAssignment.id).where(StaffAssignment.tenant_id == TID,
                StaffAssignment.user_id == user.id, StaffAssignment.org_type == scope_type,
                StaffAssignment.org_node_id == org_id, StaffAssignment.assignment_type == assignment)):
            db.add(StaffAssignment(tenant_id=TID, user_id=user.id, org_type=scope_type, org_node_id=org_id,
                assignment_type=assignment, effective_at=datetime(2020, 1, 1), status="ACTIVE"))
        claim.update(userId=str(user.id), tenantId=str(TID), activeContextId=f"role:{role.id}")


def _review_in_thread(*args):
    from app.core.context import get_tenant, set_tenant
    previous = get_tenant()
    set_tenant(TID)
    try:
        return svc.review_program(*args)
    finally:
        set_tenant(previous)


def _seed(status="COLLEGE_REVIEW"):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, College, Major, SchoolClass, TeacherStudentScope, Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="aa-r3-program-review",
                school_name="AA R3 培养方案审核学校",
                short_name="AA R3 方案",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        college_a = College(tenant_id=TID, college_name="R3 方案学院 A", code="R3PA")
        college_b = College(tenant_id=TID, college_name="R3 方案学院 B", code="R3PB")
        db.add_all([college_a, college_b])
        db.flush()
        major_a = Major(tenant_id=TID, college_id=college_a.id, major_name="R3 方案专业 A", code="R3PMA")
        major_b = Major(tenant_id=TID, college_id=college_b.id, major_name="R3 方案专业 B", code="R3PMB")
        db.add_all([major_a, major_b])
        db.flush()
        db.add_all([
            SchoolClass(tenant_id=TID, major_id=major_a.id, class_name="R3 方案 A 班", grade="2096"),
            SchoolClass(tenant_id=TID, major_id=major_b.id, class_name="R3 方案 B 班", grade="2096"),
        ])
        own = AaProgram(
            tenant_id=TID,
            program_name="R3 本院培养方案",
            major_id=major_a.id,
            grade_year="2096",
            total_credits=100,
            version=7,
            status=status,
        )
        other = AaProgram(
            tenant_id=TID,
            program_name="R3 外院培养方案",
            major_id=major_b.id,
            grade_year="2096",
            total_credits=100,
            version=9,
            status=status,
        )
        scope = TeacherStudentScope(
            tenant_id=TID,
            teacher_key=COLLEGE_USER["loginName"],
            teacher_name="R3 方案学院 A 教务",
            role_code="COLLEGE_ADMIN",
            scope_type="COLLEGE",
            ref_value=college_a.college_name,
            status="ACTIVE",
        )
        db.add_all([own, other, scope])
        _seed_review_identities(db, int(college_a.id))
        db.commit()
        return {"own": int(own.id), "other": int(other.id)}
    finally:
        db.close()


def _program(program_id):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    db = get_sessionmaker()()
    try:
        row = db.get(AaProgram, int(program_id))
        return row.status, int(row.version)
    finally:
        db.close()


def test_program_course_formation_survives_formal_write_and_read(db_mode, monkeypatch):
    from types import SimpleNamespace

    ids = _seed(status="DRAFT")
    body = SimpleNamespace(courseName="编班来源验收课程", openTermNo=1, module="专业选修", credit=2, formationMode="SELECTABLE")
    created = svc._core.add_course(ids["own"], SCHOOL_USER, body)
    assert created["formationMode"] == "SELECTABLE"
    row = svc._core.get_program(ids["own"], SCHOOL_USER)["courses"][0]
    assert row["formationMode"] == "SELECTABLE"
    svc._core.update_course(created["programCourseId"], SCHOOL_USER, SimpleNamespace(credit=3))
    assert svc._core.get_program(ids["own"], SCHOOL_USER)["courses"][0]["formationMode"] == "SELECTABLE"
    svc._core.update_course(created["programCourseId"], SCHOOL_USER, SimpleNamespace(formationMode="ADMIN_FIXED"))
    assert svc._core.get_program(ids["own"], SCHOOL_USER)["courses"][0]["formationMode"] == "ADMIN_FIXED"
    with pytest.raises(AppException) as invalid:
        svc._core.update_course(created["programCourseId"], SCHOOL_USER, SimpleNamespace(formationMode="UNKNOWN"))
    assert invalid.value.code == "VALIDATION_ERROR"
    assert svc._core.get_program(ids["own"], SCHOOL_USER)["courses"][0]["formationMode"] == "ADMIN_FIXED"
    published = _seed(status="ACTIVE")
    with pytest.raises(AppException) as locked:
        svc._core.add_course(published["own"], SCHOOL_USER, body)
    assert locked.value.code == "DATA_CONFLICT"


def _audit_count(program_id, action):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail

    db = get_sessionmaker()()
    try:
        return int(db.scalar(select(func.count(AffairsAuditTrail.id)).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "AA_PROGRAM",
            AffairsAuditTrail.biz_id == int(program_id),
            AffairsAuditTrail.action == action,
        )) or 0)
    finally:
        db.close()


def test_college_approves_own_program_one_node_only(db_mode, monkeypatch):
    ids = _seed()

    row = svc.review_program(ids["own"], COLLEGE_USER, "APPROVE")

    assert row["status"] == "ACADEMIC_REVIEW"
    assert _program(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1


def test_detail_review_node_matches_locked_command_authority(db_mode, monkeypatch):
    ids = _seed()
    assert svc.get_program(ids["own"], COLLEGE_USER)["reviewNode"]["canReview"] is True
    school_node = svc.get_program(ids["own"], SCHOOL_USER)["reviewNode"]
    assert school_node["canReview"] is False
    assert "学院审核" in school_node["reason"]
    with pytest.raises(AppException) as denied:
        svc.get_program(ids["other"], COLLEGE_USER)
    assert denied.value.code == "NO_DATA_SCOPE"
    svc.review_program(ids["own"], COLLEGE_USER, "APPROVE")
    college_node = svc.get_program(ids["own"], COLLEGE_USER)["reviewNode"]
    assert college_node["canReview"] is False
    assert "校级教务" in college_node["reason"]
    assert svc.get_program(ids["own"], SCHOOL_USER)["reviewNode"]["canReview"] is True


def test_college_return_requires_reason_and_goes_returned(db_mode, monkeypatch):
    ids = _seed()

    with pytest.raises(AppException) as exc:
        svc.review_program(ids["own"], COLLEGE_USER, "RETURN", "短")
    assert exc.value.code == "VALIDATION_ERROR"
    assert _program(ids["own"]) == ("COLLEGE_REVIEW", 7)

    row = svc.review_program(ids["own"], COLLEGE_USER, "RETURN", "课程结构需要重新核对")
    assert row["status"] == "RETURNED"
    assert _program(ids["own"]) == ("RETURNED", 7)


def test_returned_resubmit_restarts_college_review(db_mode, monkeypatch):
    ids = _seed(status="RETURNED")
    monkeypatch.setattr(svc.governance, "_ensure_program_scope", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(svc.governance, "validate_program_db", lambda *_args, **_kwargs: {
        "issues": [],
        "creditSum": 100.0,
        "counts": {"warning": 0},
        "conclusion": "PASS",
    })

    row = svc.submit_program(ids["own"], COLLEGE_USER)

    assert row["status"] == "COLLEGE_REVIEW"
    assert _program(ids["own"]) == ("COLLEGE_REVIEW", 7)


def test_college_cannot_approve_other_college_program(db_mode, monkeypatch):
    ids = _seed()

    with pytest.raises(AppException) as exc:
        svc.review_program(ids["other"], COLLEGE_USER, "APPROVE")

    assert exc.value.code == "NO_DATA_SCOPE"
    assert _program(ids["other"]) == ("COLLEGE_REVIEW", 9)
    assert _audit_count(ids["other"], "APPROVE") == 0


def test_college_cannot_immediately_cross_academic_review(db_mode, monkeypatch):
    ids = _seed()
    svc.review_program(ids["own"], COLLEGE_USER, "APPROVE")

    with pytest.raises(AppException) as exc:
        svc.review_program(ids["own"], COLLEGE_USER, "APPROVE")

    assert exc.value.code == "NO_DATA_SCOPE"
    assert _program(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1


def test_tenant_all_academic_review_publishes(db_mode, monkeypatch):
    ids = _seed(status="ACADEMIC_REVIEW")

    row = svc.review_program(ids["own"], SCHOOL_USER, "APPROVE")

    assert row["status"] == "PUBLISHED"
    assert _program(ids["own"]) == ("PUBLISHED", 7)


def test_two_same_node_reviews_produce_one_transition_and_one_audit(db_mode, monkeypatch):
    ids = _seed()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_review_in_thread, ids["own"], COLLEGE_USER, "APPROVE")
            for _ in range(2)
        ]
        successes = 0
        blocked = 0
        for future in futures:
            try:
                result = future.result(timeout=10)
                assert result["status"] == "ACADEMIC_REVIEW"
                successes += 1
            except AppException as exc:
                # The loser waits on the row lock, then sees the next-node Authority.
                # It must be blocked as the previous college reviewer, not cross the node.
                assert exc.code == "NO_DATA_SCOPE"
                blocked += 1

    assert successes == 1
    assert blocked == 1
    assert _program(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1
