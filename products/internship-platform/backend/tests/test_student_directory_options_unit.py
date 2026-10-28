"""Execute the real directory route and SQL scope without connecting to a database."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import mysql

from app.api.v1 import org_directory
from app.core.exceptions import register_exception_handlers
from app.core.security import get_current_user
from app.models import StudentProfile, TeacherStudentScope


class Rows(list):
    def all(self):
        return list(self)


@pytest.fixture
def directory(monkeypatch):
    user = {"tenantId": "12", "userId": "37", "userType": "TEACHER",
            "currentRoleCode": "COLLEGE_ADMIN", "permissions": ["internship.student.manage"]}
    db = MagicMock()
    db.__enter__.return_value = db
    queries = []
    students = [SimpleNamespace(id=9007199254740993123, real_name="合成学生",
                                student_no="00009007199254740993123")]
    grants = [SimpleNamespace(scope_type="COLLEGE", ref_id=21)]

    def scalars(query):
        if query.column_descriptions[0]["entity"] is TeacherStudentScope:
            queries.append(("scope", query))
            return Rows(grants)
        assert query.column_descriptions[0]["entity"] is StudentProfile
        queries.append(("students", query))
        return Rows(students)

    def scalar(query):
        queries.append(("count", query))
        return 31

    db.scalars.side_effect = scalars
    db.scalar.side_effect = scalar
    factory = MagicMock(return_value=db)
    monkeypatch.setattr(org_directory, "get_sessionmaker", lambda: factory)
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_current_user] = lambda: user
    app.include_router(org_directory.router, prefix="/api/v1")
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, user=user, db=db, queries=queries,
                              students=students, grants=grants, factory=factory)


def query_of(directory, kind):
    return next(query for label, query in reversed(directory.queries) if label == kind)


def sql(query):
    return str(query.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.parametrize("permission", ["internship.student.manage", "internship.batch.manage"])
def test_student_options_executes_real_scope_and_bounded_search(directory, permission):
    directory.user["permissions"] = [permission]
    response = directory.client.get("/api/v1/directory/student-options",
                                    params={"page": 2, "pageSize": 30, "keyword": "合成%_"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {"items": [{"id": "9007199254740993123", "name": "合成学生",
                               "studentNo": "00009007199254740993123"}],
                    "total": 31, "page": 2, "pageSize": 30}
    query = query_of(directory, "students")
    assert query._limit_clause.value == 30 and query._offset_clause.value == 30
    for current in (query, query_of(directory, "count")):
        rendered = sql(current)
        assert "t_student_profile.tenant_id = 12" in rendered
        assert "t_student_profile.is_deleted IS false" in rendered
        assert "t_student_profile.college_id IN (21)" in rendered
        assert "t_student_profile.status = 'ACTIVE'" in rendered
        assert "t_student_profile.current_stage IN" in rendered
        assert "t_student_profile.student_status IN ('NORMAL')" in rendered
        assert "ESCAPE '/'" in rendered
        assert "合成/%/_" in current.compile(dialect=mysql.dialect()).params.values()
    scope_sql = sql(query_of(directory, "scope"))
    assert "tenant_id = 12" in scope_sql and "user_id = 37" in scope_sql
    assert "role_code = 'COLLEGE_ADMIN'" in scope_sql


def test_selected_ids_do_not_use_first_page_and_keep_scope(directory):
    response = directory.client.get("/api/v1/directory/student-options", params={
        "ids": "31,9007199254740993123,31", "page": 9, "pageSize": 1,
        "keyword": "搜索词不能排除已选对象"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page"] == 1 and data["pageSize"] == 2
    query = query_of(directory, "students")
    assert query._limit_clause.value == 2 and query._offset_clause.value == 0
    rendered = sql(query)
    assert "t_student_profile.id IN (31, 9007199254740993123)" in rendered
    assert "t_student_profile.tenant_id = 12" in rendered
    assert "t_student_profile.college_id IN (21)" in rendered
    assert "搜索词不能排除已选对象" not in rendered


def test_unconfigured_scope_stays_empty_and_never_becomes_school_wide(directory):
    directory.grants.clear()
    directory.students.clear()
    directory.db.scalar.side_effect = lambda query: 0
    response = directory.client.get("/api/v1/directory/student-options", params={"ids": "31"})
    assert response.status_code == 200 and response.json()["data"]["items"] == []
    rendered = sql(query_of(directory, "students"))
    assert "t_student_profile.tenant_id = 12" in rendered
    assert "1 != 1" in rendered or "0 = 1" in rendered or "false" in rendered.lower()


@pytest.mark.parametrize("ids", ["", "0", "-1", "1,,2", "1, ", "１", "9223372036854775808",
                                     ",".join(map(str, range(1, 102)))])
def test_invalid_selected_ids_reject_before_query(directory, ids):
    response = directory.client.get("/api/v1/directory/student-options", params={"ids": ids})
    assert response.status_code == 422
    directory.factory.assert_not_called()


@pytest.mark.parametrize("params", [{"page": 0}, {"pageSize": 101}, {"keyword": "长" * 101}])
def test_http_query_bounds_reject_before_query(directory, params):
    assert directory.client.get("/api/v1/directory/student-options", params=params).status_code == 422
    directory.factory.assert_not_called()


@pytest.mark.parametrize("role", ["STUDENT", "PARENT", "GUARDIAN", "PLATFORM_SUPER_ADMIN"])
def test_non_school_staff_identities_cannot_use_directory(directory, role):
    directory.user.update(currentRoleCode=role, userType=role)
    assert directory.client.get("/api/v1/directory/student-options").status_code == 403
    directory.factory.assert_not_called()


def test_read_only_student_permission_does_not_expand_to_management(directory):
    directory.user["permissions"] = ["internship.student.view"]
    assert directory.client.get("/api/v1/directory/student-options").status_code == 403
    directory.factory.assert_not_called()
