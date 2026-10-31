"""学院教务的办理权限不包含实体删除；隔离 MySQL 服务与持久化回归。"""
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import academic_affairs_course_public_service as courses
from app.modules.academic_affairs.services import academic_affairs_program_service as programs


TID = 1000000000000000001


@contextmanager
def _acting(actor):
    previous = get_current_user_ctx()
    set_current_user(actor)
    try:
        yield
    finally:
        set_current_user(previous)


@pytest.fixture
def deletion_case(db_mode):
    from app.models import (AaCourse, AaCourseMaterial, AaProgram, AaProgramCourse,
                            AaProgramGraduationRequirement, AaProgramPracticeSegment,
                            College, Major, Role, RoleAssignmentScope, User, UserRole)

    previous = get_tenant()
    set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            own = College(tenant_id=TID, college_name="禁删验证本院", status="ACTIVE")
            other = College(tenant_id=TID, college_name="禁删验证外院", status="ACTIVE")
            db.add_all([own, other])
            db.flush()
            actors = {}
            for code in ("COLLEGE_ACADEMIC", "COLLEGE_ADMIN", "ACADEMIC_ADMIN", "SCHOOL_ADMIN"):
                role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == code))
                if role is None:
                    role = Role(tenant_id=TID, role_code=code, role_name=code, role_type="SYSTEM", status="ACTIVE")
                    db.add(role)
                    db.flush()
                user = User(tenant_id=TID, login_name=f"r0-delete-{code.lower()}", real_name="禁删验证教师",
                            user_type="TEACHER", password_hash="unused-in-service-test", status="ACTIVE")
                db.add(user)
                db.flush()
                link = UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE")
                db.add(link)
                db.flush()
                if code in ("COLLEGE_ACADEMIC", "COLLEGE_ADMIN"):
                    db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=user.id,
                        role_code=code, scope_type="COLLEGE", scope_id=own.id, status="ACTIVE",
                        effective_at=datetime(2020, 1, 1)))
                actors[code] = {"userId": str(user.id), "loginName": user.login_name,
                    "tenantId": str(TID), "realName": user.real_name, "userType": "TEACHER",
                    "currentRoleCode": code, "activeContextId": f"role:{role.id}"}
            objects = {}
            for label, college, suffix in (("own", own, "101"), ("other", other, "102")):
                major = Major(tenant_id=TID, college_id=college.id, major_name=f"禁删验证{label}专业", status="ACTIVE")
                db.add(major)
                db.flush()
                program = AaProgram(tenant_id=TID, program_name=f"禁删验证{label}方案", major_id=major.id,
                                    grade_year="2098", total_credits=100, status="DRAFT")
                course = AaCourse(tenant_id=TID, course_code=f"DLR{suffix}", course_name=f"禁删验证{label}课程",
                                  owner_college_id=college.id, credit=2, status="DRAFT")
                db.add_all([program, course])
                db.flush()
                rows = [
                    AaProgramCourse(tenant_id=TID, program_id=program.id, course_id=course.id, course_name="方案课程"),
                    AaProgramGraduationRequirement(tenant_id=TID, program_id=program.id, content="毕业要求"),
                    AaProgramPracticeSegment(tenant_id=TID, program_id=program.id, segment_name="实践环节"),
                    AaCourseMaterial(tenant_id=TID, course_id=course.id, material_type="OTHER", title="课程材料"),
                ]
                db.add_all(rows)
                db.flush()
                objects[label] = {"program": int(program.id), "course": int(course.id), "college": int(college.id),
                                  "rows": [(type(row), int(row.id)) for row in rows]}
            db.commit()
        yield {"actors": actors, **objects}
    finally:
        set_tenant(previous)


def _snapshot(case):
    from app.models import AffairsAuditTrail

    with get_sessionmaker()() as db:
        states = []
        for model, row_id in case["rows"]:
            row = db.get(model, row_id)
            states.append((row.is_deleted, getattr(row, "status", None), row.version))
        audit = int(db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type.in_(["AA_PROGRAM", "AA_COURSE"]),
        )) or 0)
        return states, audit


def _delete_calls(case, actor):
    ids = [row_id for _, row_id in case["rows"]]
    return (
        lambda: programs.delete_course(ids[0], actor),
        lambda: programs.delete_graduation_requirement(ids[1], actor),
        lambda: programs.delete_practice_segment(ids[2], actor),
        lambda: courses.void_course_material(ids[3], actor),
    )


def test_college_manage_keeps_add_and_edit_but_all_entity_deletes_leave_data_and_audit_unchanged(deletion_case):
    from app.models import AaCourse, AaProgramCourse, AaProgramGraduationRequirement, AaProgramPracticeSegment

    actor = deletion_case["actors"]["COLLEGE_ACADEMIC"]
    own = deletion_case["own"]
    assert has_permission(actor, "academicAffairs.program.manage")
    assert has_permission(actor, "academicAffairs.course.manage")
    with _acting(actor):
        child = programs.add_course(own["program"], actor, SimpleNamespace(courseName="学院新增课程", formationMode="ADMIN_FIXED"))
        programs.update_course(child["programCourseId"], actor, SimpleNamespace(courseName="学院编辑课程"))
        requirement = programs.create_graduation_requirement(own["program"], actor, SimpleNamespace(content="学院新增要求"))
        programs.update_graduation_requirement(requirement["requirementId"], actor, SimpleNamespace(content="学院编辑要求"))
        segment = programs.create_practice_segment(own["program"], actor, SimpleNamespace(segmentName="学院新增实践"))
        programs.update_practice_segment(segment["segmentId"], actor, SimpleNamespace(segmentName="学院编辑实践"))
        body = SimpleNamespace(courseCode="DLR103", courseName="学院新建课程", category="MAJOR_CORE", nature="REQUIRED",
                               credit=2, examMode="EXAM", hoursTotal=None, ownerCollegeId=own["college"])
        course = courses.create_course(body, actor)
        body.courseName = "学院维护课程"
        courses.update_course(course["courseId"], actor, body)
        material = courses.add_course_material(own["course"], actor, SimpleNamespace(
            materialType="OTHER", title="学院新增材料", fileId="", fileName="", remark=""))
        assert material["title"] == "学院新增材料"
        with get_sessionmaker()() as db:
            assert db.get(AaProgramCourse, int(child["programCourseId"])).course_name == "学院编辑课程"
            assert db.get(AaProgramGraduationRequirement, int(requirement["requirementId"])).content == "学院编辑要求"
            assert db.get(AaProgramPracticeSegment, int(segment["segmentId"])).segment_name == "学院编辑实践"
            assert db.get(AaCourse, int(course["courseId"])).course_name == "学院维护课程"
        before = _snapshot(own)
        for call in _delete_calls(own, actor):
            with pytest.raises(AppException) as exc:
                call()
            assert exc.value.code == "NO_PERMISSION"
            assert exc.value.http_status == 403
            assert _snapshot(own) == before


@pytest.mark.parametrize("role", ["COLLEGE_ADMIN", "ACADEMIC_ADMIN", "SCHOOL_ADMIN"])
def test_existing_roles_keep_valid_own_scope_deletion(deletion_case, role):
    actor = deletion_case["actors"][role]
    own = deletion_case["own"]
    before = _snapshot(own)
    with _acting(actor):
        for call in _delete_calls(own, actor):
            call()
    after = _snapshot(own)
    assert all(deleted for deleted, _, _ in after[0])
    assert after[1] == before[1] + 4


def test_existing_college_role_still_cannot_delete_foreign_college_objects(deletion_case):
    actor = deletion_case["actors"]["COLLEGE_ADMIN"]
    other = deletion_case["other"]
    before = _snapshot(other)
    with _acting(actor):
        for call in _delete_calls(other, actor):
            with pytest.raises(AppException) as exc:
                call()
            assert exc.value.code == "NO_DATA_SCOPE"
            assert _snapshot(other) == before
