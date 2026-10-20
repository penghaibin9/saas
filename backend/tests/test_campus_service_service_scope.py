from __future__ import annotations

import pytest


def test_direct_create_enforces_college_scope_and_profile_exposes_active_ledger(db_mode):
    from sqlalchemy import func, select

    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import (College, CsServiceStudent, Major, SchoolClass, StudentProfile,
                            TeacherStudentScope)
    from app.services import campus_service_service, affairs_profile_service

    tenant_id = 1000000000000000001
    db = get_sessionmaker()()
    try:
        college_a = College(tenant_id=tenant_id, college_name="软件学院", status="ACTIVE")
        college_b = College(tenant_id=tenant_id, college_name="机械学院", status="ACTIVE")
        db.add_all([college_a, college_b])
        db.flush()
        major_a = Major(tenant_id=tenant_id, college_id=college_a.id,
                        major_name="软件技术", status="ACTIVE")
        major_b = Major(tenant_id=tenant_id, college_id=college_b.id,
                        major_name="机械制造", status="ACTIVE")
        db.add_all([major_a, major_b])
        db.flush()
        class_a = SchoolClass(tenant_id=tenant_id, major_id=major_a.id,
                              class_name="软件2601", status="ACTIVE")
        class_b = SchoolClass(tenant_id=tenant_id, major_id=major_b.id,
                              class_name="机械2601", status="ACTIVE")
        db.add_all([class_a, class_b])
        db.flush()
        own = StudentProfile(tenant_id=tenant_id, student_no="CSCOPE-A", real_name="范围内学生",
                             college_id=college_a.id, major_id=major_a.id, class_id=class_a.id,
                             current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        outside = StudentProfile(tenant_id=tenant_id, student_no="CSCOPE-B", real_name="范围外学生",
                                 college_id=college_b.id, major_id=major_b.id, class_id=class_b.id,
                                 current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        db.add_all([own, outside])
        db.flush()
        db.add(TeacherStudentScope(tenant_id=tenant_id, teacher_key="college_admin_scope_test",
                                  role_code="COLLEGE_ADMIN", scope_type="COLLEGE",
                                  ref_value="软件学院", status="ACTIVE"))
        db.commit()
        own_id, outside_id = own.id, outside.id
    finally:
        db.close()

    set_tenant({"tenantId": str(tenant_id)})
    set_current_user({"userId": "db-998877", "loginName": "college_admin_scope_test",
                      "currentRoleCode": "COLLEGE_ADMIN"})
    try:
        # Bypass the router-installed wrapper to exercise the service's own fail-closed check.
        wrapper = campus_service_service.create_student
        core_create = wrapper.__closure__[wrapper.__code__.co_freevars.index("old_create")].cell_contents
        with pytest.raises(AppException) as denied:
            core_create({"studentId": str(outside_id)})
        assert denied.value.code == "NO_DATA_SCOPE"

        db = get_sessionmaker()()
        try:
            assert db.scalar(select(func.count()).select_from(CsServiceStudent).where(
                CsServiceStudent.student_id == outside_id,
                CsServiceStudent.tenant_id == tenant_id,
                CsServiceStudent.is_deleted.is_(False))) == 0
        finally:
            db.close()

        created = core_create({"studentId": str(own_id)})
        profile = affairs_profile_service.get_profile(own_id, {
            "userId": "db-998877", "loginName": "college_admin_scope_test",
            "currentRoleCode": "COLLEGE_ADMIN",
        })
        assert profile["serviceLedger"] == {"exists": True, "recordId": created["id"]}

        db = get_sessionmaker()()
        try:
            row = db.get(CsServiceStudent, int(created["id"]))
            assert row and row.student_id == own_id and not row.is_deleted
        finally:
            db.close()

        # Batch import passes its still-uncommitted profile through this same session.
        db = get_sessionmaker()()
        try:
            source = db.get(StudentProfile, own_id)
            pending = StudentProfile(tenant_id=tenant_id, student_no="CSCOPE-PENDING",
                                     real_name="事务内学生", college_id=source.college_id,
                                     major_id=source.major_id, class_id=source.class_id,
                                     current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
            db.add(pending)
            db.flush()
            imported = wrapper({"studentId": str(pending.id)}, db=db)
            assert imported["version"] == 0
            assert db.get(CsServiceStudent, int(imported["id"])).student_id == pending.id
            db.rollback()
        finally:
            db.close()
    finally:
        set_current_user(None)
        set_tenant(None)
