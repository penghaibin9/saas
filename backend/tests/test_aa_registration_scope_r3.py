"""P1-02 / AA-002: registration writer and main list object scope."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_dashboard_scope_facade as facade
from app.modules.academic_affairs.services import academic_affairs_registration_scope as scope_svc

TID = 1000000000000000802
COLLEGE_USER = {
    "userId": "aa-r3-college-a",
    "loginName": "aa-r3-college-a",
    "userType": "TEACHER",
    "currentRoleCode": "COLLEGE_ADMIN",
}
SCHOOL_USER = {
    "userId": "aa-r3-school",
    "loginName": "aa-r3-school",
    "userType": "TEACHER",
    "currentRoleCode": "ACADEMIC_ADMIN",
}


def _patch_tenant(monkeypatch) -> None:
    from app.core import affairs_security
    from app.modules.academic_affairs.services import academic_affairs_archive_core_service as archive_core

    monkeypatch.setattr(facade._legacy, "_tid", lambda: TID)
    monkeypatch.setattr(affairs_security, "_tid", lambda: TID)
    monkeypatch.setattr(archive_core, "_tid", lambda: TID)
    monkeypatch.setattr(scope_svc, "audit_status_change", lambda *args, **kwargs: None)

    def _status_change(db, student_id, to_status, change_type, **kwargs):
        from app.models import StudentProfile

        student = db.get(StudentProfile, int(student_id))
        before = student.student_status
        student.student_status = to_status
        return {
            "studentId": str(student_id),
            "fromStatus": before,
            "toStatus": to_status,
            "changeType": change_type,
        }

    monkeypatch.setattr(scope_svc, "change_student_status", _status_change)


def _seed():
    from app.db.session import get_sessionmaker
    from app.models import (
        AaRegistration,
        AaRegistrationBatch,
        College,
        Major,
        SchoolClass,
        StudentProfile,
        TeacherStudentScope,
        Tenant,
    )

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="aa-r3-registration",
                school_name="AA R3 注册学校",
                short_name="AA R3 注册",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        college_a = College(tenant_id=TID, college_name="R3 学院 A", code="R3A")
        college_b = College(tenant_id=TID, college_name="R3 学院 B", code="R3B")
        db.add_all([college_a, college_b])
        db.flush()
        major_a = Major(tenant_id=TID, college_id=college_a.id, major_name="R3 专业 A", code="R3MA")
        major_b = Major(tenant_id=TID, college_id=college_b.id, major_name="R3 专业 B", code="R3MB")
        db.add_all([major_a, major_b])
        db.flush()
        class_a = SchoolClass(tenant_id=TID, major_id=major_a.id, class_name="R3 A 班", grade="2095")
        class_b = SchoolClass(tenant_id=TID, major_id=major_b.id, class_name="R3 B 班", grade="2095")
        db.add_all([class_a, class_b])
        db.flush()
        student_a = StudentProfile(
            tenant_id=TID,
            student_no="R3REG-A",
            real_name="注册学生A",
            college_id=college_a.id,
            major_id=major_a.id,
            class_id=class_a.id,
            student_status="PENDING_REGISTER",
        )
        student_b = StudentProfile(
            tenant_id=TID,
            student_no="R3REG-B",
            real_name="注册学生B",
            college_id=college_b.id,
            major_id=major_b.id,
            class_id=class_b.id,
            student_status="PENDING_REGISTER",
        )
        batch = AaRegistrationBatch(
            tenant_id=TID,
            batch_name="R3 入学注册",
            register_type="ENROLL",
            status="OPEN",
        )
        scope = TeacherStudentScope(
            tenant_id=TID,
            teacher_key=COLLEGE_USER["loginName"],
            teacher_name="R3 学院 A 教务",
            role_code="COLLEGE_ADMIN",
            scope_type="COLLEGE",
            ref_value=college_a.college_name,
            status="ACTIVE",
        )
        db.add_all([student_a, student_b, batch, scope])
        db.commit()
        return {
            "batch": int(batch.id),
            "a": int(student_a.id),
            "b": int(student_b.id),
        }
    finally:
        db.close()


def _registration_count(student_id=None) -> int:
    from app.db.session import get_sessionmaker
    from app.models import AaRegistration

    db = get_sessionmaker()()
    try:
        stmt = select(func.count(AaRegistration.id)).where(AaRegistration.tenant_id == TID)
        if student_id is not None:
            stmt = stmt.where(AaRegistration.student_id == int(student_id))
        return int(db.scalar(stmt) or 0)
    finally:
        db.close()


def _profile_status(student_id):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile

    db = get_sessionmaker()()
    try:
        return db.get(StudentProfile, int(student_id)).student_status
    finally:
        db.close()


def _seed_registration(batch_id, student_id):
    from app.db.session import get_sessionmaker
    from app.models import AaRegistration

    db = get_sessionmaker()()
    try:
        db.add(AaRegistration(
            tenant_id=TID,
            batch_id=int(batch_id),
            student_id=int(student_id),
            status="REGISTERED",
        ))
        db.commit()
    finally:
        db.close()


def test_college_a_can_register_student_in_college_a(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)

    row = facade.register_student(ids["batch"], COLLEGE_USER, ids["a"])

    assert row["status"] == "REGISTERED"
    assert _registration_count(ids["a"]) == 1
    assert _profile_status(ids["a"]) == "REGISTERED"


def test_college_a_cannot_register_student_in_college_b_and_no_side_effects(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)
    before = _profile_status(ids["b"])

    with pytest.raises(AppException) as exc:
        facade.register_student(ids["batch"], COLLEGE_USER, ids["b"])

    assert exc.value.code == "NO_DATA_SCOPE"
    assert _registration_count(ids["b"]) == 0
    assert _profile_status(ids["b"]) == before


def test_registration_list_is_sql_scoped_and_total_does_not_leak_tenant_count(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)
    _seed_registration(ids["batch"], ids["a"])
    _seed_registration(ids["batch"], ids["b"])

    rows, total = facade.list_registrations(ids["batch"], COLLEGE_USER, page=1, page_size=50)

    assert total == 1
    assert [int(row["studentId"]) for row in rows] == [ids["a"]]


def test_tenant_all_keeps_schoolwide_registration_access(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)
    _seed_registration(ids["batch"], ids["a"])
    _seed_registration(ids["batch"], ids["b"])

    rows, total = facade.list_registrations(ids["batch"], SCHOOL_USER, page=1, page_size=50)

    assert total == 2
    assert {int(row["studentId"]) for row in rows} == {ids["a"], ids["b"]}


def test_existing_mutex_and_unique_constraint_still_make_double_click_one_fact(db_mode, monkeypatch):
    ids = _seed()
    _patch_tenant(monkeypatch)

    facade.register_student(ids["batch"], SCHOOL_USER, ids["a"])
    with pytest.raises(AppException) as exc:
        facade.register_student(ids["batch"], SCHOOL_USER, ids["a"])

    assert exc.value.code == "DATA_CONFLICT"
    assert _registration_count(ids["a"]) == 1
    from app.models import AaRegistration
    assert any(
        getattr(constraint, "name", None) == "uk_aa_registration"
        for constraint in AaRegistration.__table__.constraints
    )
