from __future__ import annotations

from pathlib import Path

from app.services.todo_route_registry import resolve_todo_route

ROOT = Path(__file__).resolve().parents[2]


def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_t8_teacher_todo_routes_live_in_the_single_shared_registry():
    registry = _src("backend/app/services/todo_route_registry.py")
    assert "_TEACHER_MINI" in registry
    assert 'if client == "teacherMini"' in registry
    assert '"INTERN_WEEKLY_REVIEW"' in registry
    assert '"EMPLOYMENT_FOLLOWUP"' in registry
    assert 'FOCUS_NONE' in registry
    assert '"teacherMini"' in registry[registry.index("def route_contract_snapshot"):]

    internship = resolve_todo_route("INTERN_WEEKLY_REVIEW", 17, client="teacherMini")
    assert internship == {
        "routeName": "todo-route:teacher-mini-internship-review",
        "routeParams": {"recordId": "17"},
        "query": {"recordId": "17"},
        "path": "/pages/teacher/internship-review/index",
        "focusMode": "NONE",
        "exact": False,
    }
    employment = resolve_todo_route("EMPLOYMENT_FOLLOWUP", 21, client="teacherMini")
    assert employment and employment["path"] == "/pages/teacher/employment-follow/index"
    assert employment["exact"] is False
    assert resolve_todo_route("UNKNOWN_TYPE", 1, client="teacherMini") is None


def test_t8_grouped_todos_reuse_t2_cursor_and_t3_visibility_without_offset():
    service = _src("backend/app/services/teacher_mobile_todo_grouped_service.py")
    assert "keyset._decode_cursor" in service
    assert "keyset._encode_cursor" in service
    assert "keyset._seek_after" in service
    assert "keyset._teacher_todo_visibility" in service
    assert 'todo_svc._todo_dict(row, client="teacherMini")' in service
    assert ".limit(size + 1)" in service
    assert ".offset(" not in service
    assert '"filterBadges": badges' in service
    assert "perf._group_expr()" in service


def test_t8_grouped_route_is_additive_under_existing_teacher_mobile_surface():
    route = _src("backend/app/api/v1/teacher_mobile_students.py")
    assert '@router.get("/todos/grouped-continuous"' in route
    assert "teacher_mobile_todo_grouped_service as todo_grouped_svc" in route
    assert "todo_grouped_svc.list_grouped_continuous(" in route
    assert "require_staff" in route
