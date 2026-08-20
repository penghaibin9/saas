from __future__ import annotations

import inspect

from app.models import UnifiedTodo
from app.services import teacher_mobile_todo_keyset_service as keyset_svc
from app.services import teacher_student_visibility_service as visibility


def _compile_sql(expr) -> str:
    return str(expr.compile(compile_kwargs={"literal_binds": True})).lower()


def test_t3_visibility_compiler_is_sql_only_and_reuses_scope_authority():
    source = inspect.getsource(visibility)
    assert "teacher_scope_authority.resolve_teacher_scope" in source
    assert "exists(" in source
    assert ".all()" not in source
    assert ".offset(" not in source
    assert "studentids" not in source.lower()
    assert "teacherstudentscope" not in source.lower()


def test_t3_scoped_visibility_compiles_student_class_college_and_advisor_exists(monkeypatch):
    monkeypatch.setattr(visibility, "_tid", lambda: 7)
    monkeypatch.setattr(
        visibility.teacher_scope_authority,
        "resolve_teacher_scope",
        lambda user: {
            "mode": "SCOPED",
            "studentNos": {"20260001"},
            "classNames": {"软件2301"},
            "collegeNames": {"信息工程学院"},
            "advisorUserIds": {"42"},
            "advisorNames": {"张老师"},
        },
    )

    sql = _compile_sql(visibility.compile_teacher_student_visibility(
        {"userId": "42"}, UnifiedTodo.student_id
    ))

    assert "exists" in sql
    assert "t_student_profile" in sql
    assert "student_no" in sql
    assert "t_class" in sql
    assert "class_name" in sql
    assert "t_college" in sql
    assert "college_name" in sql
    assert "t_major" in sql
    assert "t_internship_record" in sql
    assert "advisor_user_id" in sql
    assert "t_gd_student" in sql
    assert "advisor_name" in sql
    assert "tenant_id = 7" in sql


def test_t3_admin_is_explicit_tenant_wide_and_unknown_mode_fails_closed(monkeypatch):
    monkeypatch.setattr(
        visibility.teacher_scope_authority,
        "resolve_teacher_scope",
        lambda user: {"mode": "ADMIN_TENANT"},
    )
    assert _compile_sql(visibility.compile_teacher_student_visibility({}, UnifiedTodo.student_id)) == "true"

    monkeypatch.setattr(
        visibility.teacher_scope_authority,
        "resolve_teacher_scope",
        lambda user: {"mode": "UNKNOWN"},
    )
    assert _compile_sql(visibility.compile_teacher_student_visibility({}, UnifiedTodo.student_id)) == "false"


def test_t3_empty_scoped_authorization_fails_closed(monkeypatch):
    monkeypatch.setattr(
        visibility.teacher_scope_authority,
        "resolve_teacher_scope",
        lambda user: {
            "mode": "SCOPED",
            "studentNos": set(),
            "classNames": set(),
            "collegeNames": set(),
            "advisorUserIds": set(),
            "advisorNames": set(),
        },
    )
    assert _compile_sql(visibility.compile_teacher_student_visibility({}, UnifiedTodo.student_id)) == "false"


def test_t3_continuous_todo_visibility_does_not_call_legacy_materializing_scope():
    source = inspect.getsource(keyset_svc)
    helper = inspect.getsource(keyset_svc._teacher_todo_visibility)
    assert "todo_svc._visibility_cond" not in source
    assert "compile_teacher_student_visibility" in helper
    assert "UnifiedTodo.assignee_id == uid" in helper
    assert "UnifiedTodo.assignee_id == 0" in helper
