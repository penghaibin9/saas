from __future__ import annotations

import inspect

from app.services.teacher_mobile_todo_projection_service import (
    project_teacher_todo,
    project_teacher_todos,
)
import app.services.teacher_mobile_todo_projection_service as projection


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
