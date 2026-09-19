from __future__ import annotations

import inspect
from contextlib import contextmanager

import pytest

from app.core.exceptions import AppException
from app.services.teacher_mobile_todo_projection_service import (
    project_teacher_todo,
    project_teacher_todos,
)
import app.services.teacher_mobile_todo_projection_service as projection
import app.services._mobile_teacher_service_impl as teacher_impl


def test_t1_projects_server_resolved_typed_target_without_guessing():
    source = {
        "todoId": "123",
        "title": "待审请假：张三",
        "todoType": "LEAVE_REVIEW",
        "sourceModule": "student-affairs",
        "bizType": "LEAVE",
        "bizId": "456",
        "recordId": "456",
        "routeName": "todo-route:teacher-mini-leave-review",
        "routeParams": {"recordId": "456"},
        "query": {"leaveId": "456"},
        "routePath": "/pages/teacher/approval/index",
        "routeExact": False,
        "focusMode": "LIST_FOCUS",
        "allowedActions": ["OPEN", "APPROVE", "RETURN"],
        "version": 7,
        "status": "PENDING",
        "dueAt": "2026-08-20T06:00:00Z",
        "priority": "HIGH",
    }

    dto = project_teacher_todo(source)

    assert dto["todoId"] == "123"
    assert dto["bizId"] == "456"
    assert dto["id"] == "123"
    assert dto["sourceBizType"] == "LEAVE"
    assert dto["sourceBizId"] == "456"
    assert dto["expectedVersion"] == 7
    assert dto["action"] == {
        "actionKey": "todo-route:teacher-mini-leave-review",
        "target": {
            "client": "teacherMini",
            "path": "/pages/teacher/approval/index",
            "query": {"leaveId": "456"},
            "routeName": "todo-route:teacher-mini-leave-review",
            "routeParams": {"recordId": "456"},
            "focusMode": "LIST_FOCUS",
            "routeExact": False,
        },
        "allowedActions": ["OPEN", "APPROVE", "RETURN"],
        "expectedVersion": 7,
    }


def test_t1_fail_closed_when_upstream_has_no_proven_target():
    dto = project_teacher_todo({
        "todoId": "8",
        "title": "未知业务待办",
        "todoType": "UNKNOWN_TYPE",
        "bizType": "UNKNOWN",
        "bizId": "99",
        "allowedActions": ["COMPLETE"],
        "version": 3,
    })

    assert dto["sourceBizId"] == "99"
    assert dto["action"] is None
    assert dto["expectedVersion"] == 3


def test_t1_rejects_cross_client_target_and_preserves_version_zero():
    dto = project_teacher_todo({
        "todoId": "18",
        "bizId": "100",
        "version": 0,
        "routeName": "todo-route:cross-client",
        "routePath": "/pages/student/affairs/leave",
        "allowedActions": ["OPEN"],
    })
    assert dto["todoId"] == "18"
    assert dto["expectedVersion"] == 0
    assert dto["action"] is None


def test_t1_accepts_the_real_teacher_internship_subpackage_target():
    """岗位实习待办不能被投影层误判成跨端路由，否则工作台“去处理”变死按钮。"""
    dto = project_teacher_todo({
        "todoId": "28",
        "title": "第 2 周周报待批",
        "todoType": "INTERN_WEEKLY_REVIEW",
        "bizType": "WEEKLY_REPORT",
        "bizId": "44828",
        "recordId": "44828",
        "routeName": "todo-route:teacher-mini-internship-review",
        "routeParams": {"recordId": "44828"},
        "query": {"recordId": "44828"},
        "routePath": "/pages/teacher-internship/internship-review/index",
        "routeExact": False,
        "focusMode": "NONE",
        "allowedActions": ["OPEN"],
        "version": 0,
        "status": "PENDING",
    })
    assert dto["action"]["target"]["path"] == "/pages/teacher-internship/internship-review/index"
    assert dto["action"]["target"]["query"]["recordId"] == "44828"
    assert dto["action"]["allowedActions"] == ["OPEN"]


def test_t1_does_not_create_third_route_authority():
    text = inspect.getsource(projection)
    assert "resolve_todo_route" not in text
    assert "message_action_registry" not in text
    assert "todoType ==" not in text
    assert "title ==" not in text


def test_t1_batch_projection_keeps_bounded_input_only():
    rows = [{"todoId": str(i), "bizId": str(i)} for i in range(20)]
    result = project_teacher_todos(rows)
    assert len(result) == 20
    assert [item["id"] for item in result] == [str(i) for i in range(20)]


def test_teacher_internship_queue_resolves_todo_report_to_its_authorized_batch(monkeypatch):
    """A Teacher Mini todo has a report ID, not a client-trusted batch ID.

    The queue must derive its batch only after the same detail service has checked
    tenant and advisor scope; otherwise a stale/default local batch makes a real
    todo appear as an empty queue.
    """
    seen: list[tuple[str | None, str | None]] = []

    @contextmanager
    def fake_session():
        yield object()

    def fake_reports(_page, _size, *, status=None, batch_id=None, user=None):
        seen.append((status, str(batch_id)))
        return ([{"id": "44828", "status": status}] if status == "PENDING_REVIEW" else [], 1 if status == "PENDING_REVIEW" else 0)

    monkeypatch.setattr(teacher_impl, "db_enabled", lambda: True)
    monkeypatch.setattr(teacher_impl, "_session", fake_session)
    monkeypatch.setattr(teacher_impl, "resolve_teacher_scope", lambda _user: {"mode": "SCOPED"})
    monkeypatch.setattr(teacher_impl.internship_service, "get_weekly_report_detail", lambda report_id, user=None: {
        "id": str(report_id), "batchId": "47"
    })
    monkeypatch.setattr(teacher_impl.internship_service, "list_weekly_reports", fake_reports)
    monkeypatch.setattr(teacher_impl.internship_service, "list_attendance_exceptions", lambda *_args, **_kwargs: ([], 0))
    monkeypatch.setattr(teacher_impl.internship_service, "get_dashboard_summary", lambda **_kwargs: {})
    from app.modules.internship.services import internship_batch_context
    monkeypatch.setattr(internship_batch_context, "resolve_batch", lambda _db, batch_id: str(batch_id))

    result = teacher_impl.internship(
        {"userType": "TEACHER", "userId": "db-235290"}, focus_report_id="44828"
    )

    assert result["batchId"] == "47"
    assert result["weeklyReports"] == [{"id": "44828", "status": "PENDING_REVIEW"}]
    assert seen == [("PENDING_REVIEW", "47"), ("OVERDUE", "47")]


def test_teacher_internship_queue_rejects_conflicting_todo_and_batch(monkeypatch):
    monkeypatch.setattr(teacher_impl, "db_enabled", lambda: True)
    monkeypatch.setattr(teacher_impl, "resolve_teacher_scope", lambda _user: {"mode": "SCOPED"})
    monkeypatch.setattr(teacher_impl.internship_service, "get_weekly_report_detail", lambda *_args, **_kwargs: {"batchId": "47"})

    with pytest.raises(AppException) as raised:
        teacher_impl.internship(
            {"userType": "TEACHER", "userId": "db-235290"}, batch_id="48", focus_report_id="44828"
        )

    assert getattr(raised.value, "code", "") == "DATA_CONFLICT"
