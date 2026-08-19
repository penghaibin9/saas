from __future__ import annotations

import inspect

from app.api.v1 import todos as todos_api
from app.services import teacher_mobile_todo_read_service as read_svc
from app.services import teacher_mobile_todo_projection_service as projection
from app.services import workbench_snapshot_service as snapshot_svc


def test_t1_teacher_mobile_api_wires_canonical_todo_read_without_new_route_map():
    source = inspect.getsource(todos_api)
    assert 'client == "teacher-mobile"' in source
    assert "teacher_mobile_todo_read_service" in source
    assert "_teacher_v3_page" in source
    assert "_teacher_v3_detail" in source
    assert "snapshot(user, page_size=pageSize, client=route_client)" in source
    assert "resolve_todo_route" not in inspect.getsource(read_svc)
    assert "message_action_registry" not in inspect.getsource(read_svc)


def test_t1_read_page_forces_teacher_mini_client_and_keeps_bounded_page(monkeypatch):
    seen = {}

    monkeypatch.setattr(read_svc.teacher_guard, "_require_teacher", lambda user: user)

    def fake_list(user, status=None, todo_type=None, page=1, page_size=20, *, client="pc"):
        seen.update({
            "user": user,
            "status": status,
            "todo_type": todo_type,
            "page": page,
            "page_size": page_size,
            "client": client,
        })
        return ([{
            "todoId": "9",
            "title": "待处理事项",
            "todoType": "UNKNOWN",
            "bizId": "99",
            "recordId": "99",
            "version": 2,
        }], 41)

    monkeypatch.setattr(read_svc.todo_svc, "list_todos", fake_list)
    result = read_svc.list_page(
        {"userId": "7", "userType": "TEACHER"},
        status="PENDING",
        todo_type="UNKNOWN",
        page=2,
        page_size=20,
    )

    assert seen["client"] == "teacherMini"
    assert seen["page"] == 2
    assert seen["page_size"] == 20
    assert result["total"] == 41
    assert result["hasMore"] is True
    assert len(result["items"]) == 1
    assert result["items"][0]["action"] is None


def test_t1_projection_is_additive_and_fail_closed_for_cross_client_target():
    source = {
        "todoId": "17",
        "title": "兼容旧客户端",
        "bizType": "LEAVE",
        "bizId": "88",
        "recordId": "88",
        "version": 0,
        "routeName": "todo-route:bad-cross-client",
        "routePath": "/pages/student/affairs/leave",
        "query": {"recordId": "88"},
        "allowedActions": ["OPEN"],
    }

    dto = projection.project_teacher_todo(source)
    assert dto["todoId"] == "17"
    assert dto["bizId"] == "88"
    assert dto["sourceBizId"] == "88"
    assert dto["expectedVersion"] == 0
    assert dto["action"] is None


def test_t1_router_keeps_frozen_paginate_shape():
    source = inspect.getsource(todos_api._teacher_v3_page)
    assert "paginate(" in source
    assert 'data["items"]' in source
    assert 'data["total"]' in source


def test_t1_workbench_snapshot_serializes_todos_with_requested_client():
    source = inspect.getsource(snapshot_svc.snapshot)
    assert 'client: str = "pc"' in source
    assert "_todo_dict(item, client=client)" in source
    assert "client not in _ALLOWED_CLIENTS" in source
