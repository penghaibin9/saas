"""P1-03 / AA-005 targeted MySQL regression for program two-level review Authority."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_program_service as svc

TID = 1000000000000000805
COLLEGE_USER = {
    "userId": "aa-r3-program-college-a",
    "loginName": "aa-r3-program-college-a",
    "userType": "TEACHER",
    "currentRoleCode": "COLLEGE_ADMIN",
}
SCHOOL_USER = {
    "userId": "aa-r3-program-school",
    "loginName": "aa-r3-program-school",
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
    _patch_tenant(monkeypatch)

    row = svc.review_program(ids["own"], COLLEGE_USER, "APPROVE")

    assert row["status"] == "ACADEMIC_REVIEW"
    assert _program(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1


def test_college_return_requires_reason_and_goes_returned(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)

    with pytest.raises(AppException) as exc:
        svc.review_program(ids["own"], COLLEGE_USER, "RETURN", "短")
    assert exc.value.code == "VALIDATION_ERROR"
    assert _program(ids["own"]) == ("COLLEGE_REVIEW", 7)

    row = svc.review_program(ids["own"], COLLEGE_USER, "RETURN", "课程结构需要重新核对")
    assert row["status"] == "RETURNED"
    assert _program(ids["own"]) == ("RETURNED", 7)


def test_returned_resubmit_restarts_college_review(db_mode, monkeypatch):
    ids = _seed(status="RETURNED")
    _patch_tenant(monkeypatch)
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
    _patch_tenant(monkeypatch)

    with pytest.raises(AppException) as exc:
        svc.review_program(ids["other"], COLLEGE_USER, "APPROVE")

    assert exc.value.code == "NO_DATA_SCOPE"
    assert _program(ids["other"]) == ("COLLEGE_REVIEW", 9)
    assert _audit_count(ids["other"], "APPROVE") == 0


def test_college_cannot_immediately_cross_academic_review(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)
    svc.review_program(ids["own"], COLLEGE_USER, "APPROVE")

    with pytest.raises(AppException) as exc:
        svc.review_program(ids["own"], COLLEGE_USER, "APPROVE")

    assert exc.value.code == "NO_DATA_SCOPE"
    assert _program(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1


def test_tenant_all_academic_review_publishes(db_mode, monkeypatch):
    ids = _seed(status="ACADEMIC_REVIEW")
    _patch_tenant(monkeypatch)

    row = svc.review_program(ids["own"], SCHOOL_USER, "APPROVE")

    assert row["status"] == "PUBLISHED"
    assert _program(ids["own"]) == ("PUBLISHED", 7)


def test_two_same_node_reviews_produce_one_transition_and_one_audit(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(svc.review_program, ids["own"], COLLEGE_USER, "APPROVE")
            for _ in range(2)
        ]
        successes = 0
        conflicts = 0
        for future in futures:
            try:
                result = future.result(timeout=10)
                assert result["status"] == "ACADEMIC_REVIEW"
                successes += 1
            except AppException as exc:
                assert exc.code == "APPROVAL_VERSION_CONFLICT"
                conflicts += 1

    assert successes == 1
    assert conflicts == 1
    assert _program(ids["own"]) == ("ACADEMIC_REVIEW", 7)
    assert _audit_count(ids["own"], "APPROVE") == 1
