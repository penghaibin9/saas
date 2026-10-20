"""SR025 candidate: real recognition read service, independent in-memory SQLite only.

Copy to backend/tests after the owner accepts the service/router patch. No db_mode,
global engine or external database. Identity guards and target resolver stay real.
"""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_recognition_read_service as read_service
from app.modules.academic_affairs.services import academic_affairs_recognition_service as public_service

TID = 1000000000000000001
STUDENT_ID = 9007199254740997
COURSE_ID = 9007199254741001


@pytest.fixture
def course_db(monkeypatch):
    from app.models import AaCourse, StudentProfile

    engine = create_engine("sqlite+pysqlite:///:memory:")
    for model in (AaCourse, StudentProfile):
        model.__table__.create(engine)
    old_tenant, old_user = get_tenant(), get_current_user_ctx()
    user = {"userId": "sr025-fixture", "userType": "STUDENT", "studentId": str(STUDENT_ID),
            "tenantId": str(TID), "studentNo": "deliberately-not-the-profile-number"}
    set_tenant(TID)
    set_current_user(user)
    with Session(engine) as db:
        db.add_all([
            StudentProfile(id=STUDENT_ID, tenant_id=TID, student_no="SR025", real_name="本人"),
            StudentProfile(id=STUDENT_ID + 1, tenant_id=TID + 1, student_no="SR025-OTHER", real_name="同名"),
            StudentProfile(id=STUDENT_ID + 2, tenant_id=TID, student_no="SR025-DELETED", real_name="已删", is_deleted=True),
            AaCourse(id=COURSE_ID, tenant_id=TID, course_code="SAME", course_name="同名课程", version=1, status="DISABLED"),
            AaCourse(id=COURSE_ID + 1, tenant_id=TID, course_code="SAME", course_name="同名课程", version=2, status="DRAFT"),
            AaCourse(id=COURSE_ID + 2, tenant_id=TID, course_code="OTHER", course_name="同名课程", version=1),
            AaCourse(id=COURSE_ID + 3, tenant_id=TID + 1, course_code="SAME", course_name="同名课程", version=3),
            AaCourse(id=COURSE_ID + 4, tenant_id=TID, course_code="SAME", course_name="同名课程", version=4, is_deleted=True),
            AaCourse(id=COURSE_ID + 5, tenant_id=TID, course_code="PCT%_", course_name="百分比与下划线 /", version=1),
            AaCourse(id=COURSE_ID + 6, tenant_id=TID, course_code=" ", course_name="坏身份", version=1),
            AaCourse(id=COURSE_ID + 7, tenant_id=TID, course_code="ZERO", course_name="零版本", version=0),
        ])
        db.commit()
        statements = []

        def record(_conn, _cursor, sql, params, _context, _many):
            statements.append((sql, params))

        event.listen(engine, "before_cursor_execute", record)

        @contextmanager
        def memory_session():
            yield db

        # Swap the session source only; canonical identity and tenant predicates stay active.
        monkeypatch.setattr(public_service, "session", memory_session)
        try:
            yield db, user, statements
        finally:
            event.remove(engine, "before_cursor_execute", record)
            set_current_user(old_user)
            set_tenant(old_tenant)
    engine.dispose()


def test_concrete_versions_keep_large_string_ids_without_plan_or_status_gate(course_db):
    db, user, _ = course_db
    items, total = read_service.student_target_courses(user, "SAME")
    assert total == 2
    assert items == [
        {"courseId": str(COURSE_ID + 1), "courseCode": "SAME", "courseName": "同名课程", "version": 2},
        {"courseId": str(COURSE_ID), "courseCode": "SAME", "courseName": "同名课程", "version": 1},
    ]
    # The same formal resolver accepts these specific IDs; a display label never matches identity.
    for row in items:
        course = public_service._resolve_target(db, SimpleNamespace(targetCourseId=row["courseId"],
                                                                   targetCourseName="错误标签"))
        assert str(course.id) == row["courseId"]
        assert course.version == row["version"]


def test_sql_filters_before_count_and_limit_offset(course_db):
    _db, user, statements = course_db
    page1, total1 = read_service.student_target_courses(user, "同名", page=1, page_size=2)
    page2, total2 = read_service.student_target_courses(user, "同名", page=2, page_size=2)
    assert total1 == total2 == 3
    assert len(page1) == 2 and len(page2) == 1
    assert not ({r["courseId"] for r in page1} & {r["courseId"] for r in page2})
    counts = [sql for sql, _ in statements if "count(" in sql.lower()]
    pages = [sql for sql, _ in statements if "FROM t_aa_course" in sql and "count(" not in sql.lower()]
    assert len(counts) == len(pages) == 2
    assert all("tenant_id" in sql and "is_deleted" in sql and "LIKE" in sql for sql in counts + pages)
    assert all("LIMIT" in sql and "OFFSET" in sql and "ORDER BY" in sql for sql in pages)
    assert all("LIMIT" not in sql for sql in counts)


@pytest.mark.parametrize("keyword", ["%", "_", "/"])
def test_keyword_is_literal_and_not_sql_wildcard(course_db, keyword):
    _db, user, _ = course_db
    items, total = read_service.student_target_courses(user, keyword)
    assert total == 1
    assert items[0]["courseId"] == str(COURSE_ID + 5)


def test_empty_keyword_and_page_beyond_end(course_db):
    _db, user, _ = course_db
    items, total = read_service.student_target_courses(user, "  ")
    assert total == len(items) == 4
    items, total = read_service.student_target_courses(user, page=20, page_size=2)
    assert items == [] and total == 4


@pytest.mark.parametrize("student_id", [STUDENT_ID + 1, STUDENT_ID + 2, STUDENT_ID + 999])
def test_foreign_deleted_missing_profile_cannot_read_courses(course_db, student_id):
    _db, user, statements = course_db
    user = {**user, "studentId": str(student_id), "studentNo": None}
    set_current_user(user)
    with pytest.raises(AppException) as exc:
        read_service.student_target_courses(user)
    assert exc.value.http_status == 404
    assert not any("FROM t_aa_course" in sql for sql, _ in statements)


@pytest.mark.parametrize("params", [{"page": 0}, {"page": True}, {"page_size": 0},
                                    {"page_size": 101}, {"page_size": "20"},
                                    {"keyword": "x" * 101}, {"keyword": {"bad": "type"}}])
def test_service_validates_before_opening_session(monkeypatch, params):
    def forbidden_session():
        raise AssertionError("invalid input must not open a database session")

    monkeypatch.setattr(public_service, "session", forbidden_session)
    with pytest.raises(AppException) as exc:
        read_service.student_target_courses({"userType": "STUDENT"}, **params)
    assert exc.value.http_status == 400


@pytest.mark.parametrize("user", [None, {"userType": "TEACHER"}, {"userType": "ADMIN"}])
def test_existing_student_guard_rejects_nonstudent_before_session(monkeypatch, user):
    def forbidden_session():
        raise AssertionError("nonstudent must not open a database session")

    monkeypatch.setattr(public_service, "session", forbidden_session)
    with pytest.raises(AppException) as exc:
        read_service.student_target_courses(user)
    assert exc.value.http_status == 403


def test_catalog_choice_is_revalidated_after_deletion_or_foreign_id(course_db):
    from app.models import AaCourse

    db, user, _ = course_db
    items, _ = read_service.student_target_courses(user, "SAME")
    picked = items[0]
    db.get(AaCourse, int(picked["courseId"])).is_deleted = True
    db.flush()
    for course_id in [picked["courseId"], str(COURSE_ID + 3)]:
        with pytest.raises(AppException) as exc:
            public_service._resolve_target(db, SimpleNamespace(targetCourseId=course_id))
        assert exc.value.http_status == 400


def test_student_course_route_reuses_guard_and_bounds():
    from app.core.commercial_surface_module_gate import enforce_commercial_surface_access
    from app.modules.academic_affairs.routers import academic_affairs as legacy
    from app.modules.academic_affairs.routers import grade_recognition_router

    matches = [r for r in grade_recognition_router.router.routes
               if r.path == "/academic-affairs/grade-recognitions/student/course-options"]
    assert len(matches) == 1
    route = matches[0]
    assert route.methods == {"GET"}
    assert [d.call for d in route.dependant.dependencies] == [
        enforce_commercial_surface_access,
        legacy._require_student,
    ]
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(grade_recognition_router.router)
    app.dependency_overrides[legacy._require_student] = lambda: {"userType": "STUDENT"}
    with TestClient(app) as client:
        for query in ["page=0", "pageSize=0", "pageSize=101", "keyword=" + "a" * 101]:
            response = client.get(route.path + "?" + query)
            assert response.status_code == 422
