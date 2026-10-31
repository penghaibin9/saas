"""R0 学院教务实际办理边界：真实发布权限、正常身份接口与同对象回读。

夹具只在 db_mode 指定的隔离 MySQL 建立虚构前置对象，不代替浏览器验收。
"""
from datetime import datetime, timedelta
import secrets
import time

import pytest
from sqlalchemy import select

from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
from app.core.security import create_access_token, decode_token, hash_password
from app.db.session import get_engine, get_sessionmaker


TID = 1000000000000000001
PREFIX = "/api/v1/academic-affairs"
COMPONENTS = [
    {"code": "PROJECT", "name": "项目考核", "weight": 40.0, "required": True, "order": 1},
    {"code": "FINAL", "name": "期末考核", "weight": 60.0, "required": True, "order": 2},
]


def _data(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


@pytest.fixture
def college_actions(db_mode, client):
    from app.core.config import settings
    from app.models import (AaCourse, AaGradeTask, AaTeachingTask, AaTeachingTaskBatch,
                            AaTerm, College, Major, Role, RoleAssignmentScope, SchoolClass,
                            StudentProfile, User, UserRole)
    from app.services.auth_service_db import _claims, _role_contexts
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as classes

    assert get_engine().dialect.name == "mysql"
    old_tenant, old_user = get_tenant(), get_current_user_ctx()
    set_tenant({"tenantId": str(TID)})
    try:
        with get_sessionmaker()() as db:
            colleges, school_classes = [], []
            for suffix in ("本院", "外院"):
                college = College(tenant_id=TID, college_name=f"R0{suffix}", status="ACTIVE")
                db.add(college)
                db.flush()
                major = Major(tenant_id=TID, college_id=college.id, major_name=f"R0{suffix}专业")
                db.add(major)
                db.flush()
                school_class = SchoolClass(tenant_id=TID, major_id=major.id,
                    class_name=f"R0{suffix}班", grade="2026", status="ACTIVE", class_status="NORMAL")
                db.add(school_class)
                db.flush()
                colleges.append(college)
                school_classes.append(school_class)

            roles = {}
            for code in ("COLLEGE_ACADEMIC", "ACADEMIC_TEACHER"):
                role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == code,
                                                    Role.is_deleted.is_(False)))
                if role is None:
                    role = Role(tenant_id=TID, role_code=code, role_name=code, role_type="SYSTEM", status="ACTIVE")
                    db.add(role)
                    db.flush()
                roles[code] = role
            users, links = {}, {}
            password = hash_password(secrets.token_urlsafe(24))
            for label, code, college_index in (
                ("college", "COLLEGE_ACADEMIC", 0), ("other_college", "COLLEGE_ACADEMIC", 1),
                ("unappointed", "COLLEGE_ACADEMIC", 0), ("unscoped", "COLLEGE_ACADEMIC", None),
                ("school_scoped", "COLLEGE_ACADEMIC", None),
                ("teacher", "ACADEMIC_TEACHER", None), ("other_teacher", "ACADEMIC_TEACHER", None),
            ):
                user = User(tenant_id=TID, login_name=f"r0_actions_{label}", real_name=f"R0-{label}",
                            password_hash=password, user_type="TEACHER", status="ACTIVE", must_change_password=False)
                db.add(user)
                db.flush()
                link = UserRole(tenant_id=TID, user_id=user.id, role_id=roles[code].id, status="ACTIVE")
                db.add(link)
                db.flush()
                if college_index is not None:
                    db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=user.id,
                        role_code=code, scope_type="COLLEGE", scope_id=colleges[college_index].id,
                        effective_at=datetime.utcnow() - timedelta(days=1), status="ACTIVE"))
                elif label == "school_scoped":
                    db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=user.id,
                        role_code=code, scope_type="SCHOOL", scope_id=0,
                        effective_at=datetime.utcnow() - timedelta(days=1), status="ACTIVE"))
                users[label], links[label] = user, link
            colleges[0].secretary_id = users["college"].id
            colleges[1].secretary_id = users["other_college"].id
            term = AaTerm(tenant_id=TID, year_code="2098-2099", term_no=1, term_name="R0办理验证学期",
                start_date=datetime.utcnow() - timedelta(days=1), end_date=datetime.utcnow() + timedelta(days=120),
                teaching_weeks=18, status="PUBLISHED", is_current=True)
            db.add(term)
            db.flush()
            students = []
            for index in (0, 1):
                student = StudentProfile(tenant_id=TID, student_no=f"R0-ACTIONS-{index}", real_name=f"R0学生{index}",
                    college_id=colleges[index].id, class_id=school_classes[index].id, student_status="NORMAL", status="ACTIVE")
                db.add(student)
                students.append(student)
            db.flush()
            ids = {"grade": [], "assign": [], "batch": [], "students": [int(row.id) for row in students]}
            for index in (0, 1):
                course = AaCourse(tenant_id=TID, course_code=f"R0-ACTIONS-{index}", course_name=f"R0课程{index}",
                                  owner_college_id=colleges[index].id, status="ENABLED")
                db.add(course)
                db.flush()
                for purpose in ("grade", "assign"):
                    batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, college_id=colleges[index].id,
                        batch_name=f"R0-{purpose}-{index}", status="APPROVED" if purpose == "grade" else "DRAFT")
                    db.add(batch)
                    db.flush()
                    task = AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=course.id,
                        course_code=course.course_code, course_name=course.course_name,
                        class_id=school_classes[index].id, teaching_class_code=f"R0-{purpose}-{index}",
                        teaching_class_name=f"R0教学班{purpose}{index}", formation_mode="ADMIN_FIXED",
                        teacher_key=users["teacher"].login_name if purpose == "grade" else None,
                        teacher_name=users["teacher"].real_name if purpose == "grade" else None,
                        start_week=1, end_week=18, status="READY" if purpose == "grade" else "PENDING_ASSIGN")
                    db.add(task)
                    db.flush()
                    if purpose == "grade":
                        classes.ensure_teaching_class_for_task(db, task.id)
                        grade = AaGradeTask(tenant_id=TID, teaching_task_id=task.id, term_id=term.id,
                            term_code=term.year_code, course_id=course.id, course_name=course.course_name,
                            class_id=school_classes[index].id, teacher_key=users["teacher"].login_name,
                            status="NOT_STARTED", deadline_at=datetime.utcnow() + timedelta(days=7))
                        db.add(grade)
                        db.flush()
                        ids["grade"].append(int(grade.id))
                    else:
                        ids["assign"].append(int(task.id))
                        ids["batch"].append(int(batch.id))
            db.commit()
            headers, actors = {}, {}
            for label, user in users.items():
                contexts = _role_contexts(db, user)
                role_code = "ACADEMIC_TEACHER" if label in ("teacher", "other_teacher") else "COLLEGE_ACADEMIC"
                context = next(item for item in contexts if item["roleCode"] == role_code)
                token = create_access_token(_claims(db, user, context, contexts, "PC"))
                headers[label] = {"Authorization": "Bearer " + token}
                actors[label] = decode_token(token)
            ids["teacher_key"] = users["teacher"].login_name
            ids["teacher_name"] = users["teacher"].real_name
            ids["college_user_id"] = int(users["college"].id)
        interval = 1.05 / max(1, min(settings.USER_API_RATE_LIMIT_PER_SECOND, settings.TENANT_API_RATE_LIMIT_PER_SECOND))
        last_request = 0.0

        def request(label, method, path, **kwargs):
            nonlocal last_request
            time.sleep(max(0, interval - (time.monotonic() - last_request)))
            response = client.request(method, PREFIX + path, headers=headers[label], **kwargs)
            last_request = time.monotonic()
            return response

        yield {**ids, "request": request, "actors": actors}
    finally:
        set_tenant(old_tenant)
        set_current_user(old_user)


def test_college_assigns_teacher_with_assign_only_and_keeps_scope_and_appointment(college_actions):
    from app.core.permissions import has_permission
    from app.models import AaTeachingClass, AaTeachingTask

    case, call = college_actions, college_actions["request"]
    actor = case["actors"]["college"]
    assert has_permission(actor, "academicAffairs.teachingTask.assign")
    assert not has_permission(actor, "academicAffairs.teachingTask.manage")
    body = {"teacherKey": case["teacher_key"], "teacherName": case["teacher_name"]}
    for label, task_id in (("college", case["assign"][1]), ("unscoped", case["assign"][0]),
                           ("unappointed", case["assign"][0])):
        response = call(label, "POST", f"/teaching-tasks/{task_id}/assign", json=body)
        assert response.status_code == 403, response.text
    result = _data(call("college", "POST", f"/teaching-tasks/{case['assign'][0]}/assign", json=body))
    assert result["teachingClassProjection"]["ok"] is True
    workbench = _data(call("college", "GET", f"/teaching-task-batches/{case['batch'][0]}/workbench"))
    assert workbench["actions"]["canAssign"] is True
    assert workbench["actions"]["canVoidDraft"] is False
    with get_sessionmaker()() as db:
        assert db.get(AaTeachingTask, case["assign"][0]).teacher_key == case["teacher_key"]
        assert db.get(AaTeachingTask, case["assign"][1]).teacher_key is None
        assert db.scalar(select(AaTeachingClass.id).where(AaTeachingClass.teaching_task_id == case["assign"][0]))


def test_college_scheme_roundtrips_to_teacher_and_freezes_after_first_score(college_actions):
    case, call = college_actions, college_actions["request"]
    path = f"/grade-tasks/{case['grade'][0]}"
    saved = _data(call("college", "PUT", path + "/scheme", json={"components": COMPONENTS}))
    teacher_read = _data(call("teacher", "GET", path + "/scheme"))
    assert teacher_read["schemeId"] == saved["schemeId"]
    assert teacher_read["components"] == COMPONENTS
    score_body = {"studentId": case["students"][0], "scores": {"PROJECT": 80, "FINAL": 90}}
    assert call("college", "POST", path + "/component-scores", json=score_body).status_code == 403
    entered = _data(call("teacher", "POST", path + "/component-scores", json=score_body))
    assert entered["recordTotalScore"] == 86
    locked = _data(call("college", "GET", path + "/scheme"))
    assert locked["status"] == "LOCKED" and locked["editable"] is False
    changed = [{**COMPONENTS[0], "weight": 50.0}, {**COMPONENTS[1], "weight": 50.0}]
    assert call("college", "PUT", path + "/scheme", json={"components": changed}).status_code == 409
    assert _data(call("teacher", "GET", path + "/scheme"))["components"] == COMPONENTS


def test_scheme_rejects_foreign_college_unconfigured_scope_and_other_teacher(college_actions):
    case, call = college_actions, college_actions["request"]
    for label, grade_id in (("college", case["grade"][1]), ("other_college", case["grade"][0]),
                            ("unscoped", case["grade"][0]), ("school_scoped", case["grade"][1]),
                            ("other_teacher", case["grade"][0])):
        path = f"/grade-tasks/{grade_id}/scheme"
        assert call(label, "GET", path + "?scopeType=SCHOOL").status_code == 403
        assert call(label, "PUT", path, json={"components": COMPONENTS}).status_code == 403


def test_college_cannot_activate_schoolwide_effective_grade_or_gpa_policy(college_actions):
    from app.core.permissions import has_permission
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy
    from app.models.academic_affairs_gpa_policy import AaGpaPointPolicy

    call, actor = college_actions["request"], college_actions["actors"]["college"]
    assert has_permission(actor, "academicAffairs.grade.scheme.manage")
    assert not has_permission(actor, "academicAffairs.grade.policy.manage")
    with get_sessionmaker()() as db:
        before = (db.query(AaEffectiveGradePolicy).count(), db.query(AaGpaPointPolicy).count())
    for path, payload in (("/grade-policies/activate", {"attemptStrategy": "LATEST_ATTEMPT"}),
                           ("/gpa-policies/activate", {"scaleType": "LINEAR"})):
        response = call("college", "POST", path, json=payload)
        assert response.status_code == 403, response.text
    with get_sessionmaker()() as db:
        assert (db.query(AaEffectiveGradePolicy).count(), db.query(AaGpaPointPolicy).count()) == before


def test_scheme_scope_is_rechecked_after_assignment_scope_is_revoked(college_actions):
    from app.models import RoleAssignmentScope

    case, call = college_actions, college_actions["request"]
    path = f"/grade-tasks/{case['grade'][0]}/scheme"
    _data(call("college", "GET", path))
    with get_sessionmaker()() as db:
        scope = db.scalar(select(RoleAssignmentScope).where(
            RoleAssignmentScope.tenant_id == TID, RoleAssignmentScope.user_id == case["college_user_id"],
            RoleAssignmentScope.role_code == "COLLEGE_ACADEMIC"))
        scope.status = "REVOKED"
        db.commit()
    assert call("college", "GET", path).status_code == 403
    assert call("college", "PUT", path, json={"components": COMPONENTS}).status_code == 403
