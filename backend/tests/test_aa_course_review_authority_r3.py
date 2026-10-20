"""P1-04 / AA-006 targeted MySQL regression for course two-level review Authority."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_course_public_service as svc

TID = 1000000000000000806
COLLEGE_USER = {
    "userId": "aa-r3-course-college-a",
    "loginName": "aa-r3-course-college-a",
    "userType": "TEACHER",
    "currentRoleCode": "COLLEGE_ADMIN",
}
SCHOOL_USER = {
    "userId": "aa-r3-course-school",
    "loginName": "aa-r3-course-school",
    "userType": "TEACHER",
    "currentRoleCode": "ACADEMIC_ADMIN",
}


def _patch_tenant(monkeypatch) -> None:
    from app.core import affairs_security

    monkeypatch.setattr(svc, "_tid", lambda: TID)
    monkeypatch.setattr(svc._core, "_tid", lambda: TID)
    monkeypatch.setattr(affairs_security, "_tid", lambda: TID)


def _seed(status="COLLEGE_REVIEW"):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, College, TeacherStudentScope, Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="aa-r3-course-review",
                school_name="AA R3 课程审核学校",
                short_name="AA R3 课程",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        college_a = College(tenant_id=TID, college_name="R3 课程学院 A", code="R3CA")
        college_b = College(tenant_id=TID, college_name="R3 课程学院 B", code="R3CB")
        db.add_all([college_a, college_b])
        db.flush()
        own = AaCourse(
            tenant_id=TID,
            course_code="R3C601",
            course_name="R3 本院课程",
            category="MAJOR_CORE",
            nature="REQUIRED",
            credit=3,
            exam_mode="EXAM",
            owner_college_id=college_a.id,
            version=7,
            status=status,
        )
        other = AaCourse(
            tenant_id=TID,
            course_code="R3C602",
            course_name="R3 外院课程",
            category="MAJOR_CORE",
            nature="REQUIRED",
            credit=3,
            exam_mode="EXAM",
            owner_college_id=college_b.id,
            version=9,
            status=status,
        )
        scope = TeacherStudentScope(
            tenant_id=TID,
            teacher_key=COLLEGE_USER["loginName"],
            teacher_name="R3 课程学院 A 教务",
            role_code="COLLEGE_ADMIN",
            scope_type="COLLEGE",
            ref_value=college_a.college_name,
            status="ACTIVE",
        )
        db.add_all([own, other, scope])
        db.commit()
        return {"own": int(own.id), "other": int(other.id)}
    finally:
        db.close()


def _course(course_id):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    db = get_sessionmaker()()
    try:
        row = db.get(AaCourse, int(course_id))
        return row.status, int(row.version)
    finally:
        db.close()


def _audit_count(course_id, action):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail

    db = get_sessionmaker()()
    try:
        return int(db.scalar(select(func.count(AffairsAuditTrail.id)).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "AA_COURSE",
            AffairsAuditTrail.biz_id == int(course_id),
            AffairsAuditTrail.action == action,
        )) or 0)
    finally:
        db.close()


def test_college_approves_own_course_to_academic_review(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)

    row = svc.review_course(ids["own"], COLLEGE_USER, "APPROVE")

    assert row["status"] == "ACADEMIC_REVIEW"
    assert _course(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1


def test_college_return_course_and_resubmit_restarts_college(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)

    with pytest.raises(AppException) as exc:
        svc.review_course(ids["own"], COLLEGE_USER, "RETURN", "短")
    assert exc.value.code == "VALIDATION_ERROR"
    assert _course(ids["own"]) == ("COLLEGE_REVIEW", 7)

    returned = svc.review_course(ids["own"], COLLEGE_USER, "RETURN", "课程信息需要重新核对")
    assert returned["status"] == "RETURNED"
    assert _course(ids["own"]) == ("RETURNED", 7)

    submitted = svc.submit_course(ids["own"], COLLEGE_USER)
    assert submitted["status"] == "COLLEGE_REVIEW"
    assert _course(ids["own"]) == ("COLLEGE_REVIEW", 7)


def test_college_cannot_review_other_college_course(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)

    with pytest.raises(AppException) as exc:
        svc.review_course(ids["other"], COLLEGE_USER, "APPROVE")

    assert exc.value.code == "NO_DATA_SCOPE"
    assert _course(ids["other"]) == ("COLLEGE_REVIEW", 9)
    assert _audit_count(ids["other"], "APPROVE") == 0


def test_college_cannot_cross_academic_review(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)
    svc.review_course(ids["own"], COLLEGE_USER, "APPROVE")

    with pytest.raises(AppException) as exc:
        svc.review_course(ids["own"], COLLEGE_USER, "APPROVE")

    assert exc.value.code == "NO_DATA_SCOPE"
    assert _course(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1


def test_tenant_all_academic_review_enables_course(db_mode, monkeypatch):
    ids = _seed(status="ACADEMIC_REVIEW")
    _patch_tenant(monkeypatch)

    row = svc.review_course(ids["own"], SCHOOL_USER, "APPROVE")

    assert row["status"] == "ENABLED"
    assert _course(ids["own"]) == ("ENABLED", 7)


def test_concurrent_same_node_review_is_single_transition(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(svc.review_course, ids["own"], COLLEGE_USER, "APPROVE")
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
                assert exc.code == "NO_DATA_SCOPE"
                blocked += 1

    assert successes == 1
    assert blocked == 1
    assert _course(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1


def test_course_business_version_is_unchanged_by_review(db_mode, monkeypatch):
    ids = _seed(status="ACADEMIC_REVIEW")
    _patch_tenant(monkeypatch)

    svc.review_course(ids["own"], SCHOOL_USER, "APPROVE")

    assert _course(ids["own"]) == ("ENABLED", 7)
