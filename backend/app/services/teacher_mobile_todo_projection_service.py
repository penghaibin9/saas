"""Teacher Miniapp V3 T1 typed Todo projection.

This module deliberately owns no route table and resolves no route itself.  It only
projects the already-resolved fields emitted by ``workbench_todo_service`` into the
Teacher V3 DTO shape.  Route authority remains in ``todo_route_registry``; the
shared MobileAction adapter remains owned by Student V3 until the T8 handoff.

Pre-handoff rule: if the upstream DTO cannot prove a target, ``action`` is ``None``.
The teacher client must never infer a route from title/group/todoType.
"""
from __future__ import annotations

from typing import Any


TEACHER_MINI_CLIENT = "teacherMini"
FOCUS_NONE = "NONE"


def _clean(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _expected_version(todo: dict) -> int | None:
    value = todo.get("expectedVersion", todo.get("version"))
    if value in (None, ""):
        return None
    try:
        version = int(value)
    except (TypeError, ValueError):
        return None
    return version if version > 0 else None


def _resolved_target(todo: dict) -> dict | None:
    """Pass through a server-resolved target without inventing route semantics."""
    path = _clean(todo.get("routePath"))
    route_name = _clean(todo.get("routeName"))
    if not path or not route_name:
        return None

    focus_mode = _clean(todo.get("focusMode")) or FOCUS_NONE
    query = todo.get("query") if isinstance(todo.get("query"), dict) else {}
    route_params = todo.get("routeParams") if isinstance(todo.get("routeParams"), dict) else {}
    return {
        "client": TEACHER_MINI_CLIENT,
        "path": path,
        "query": dict(query),
        "routeName": route_name,
        "routeParams": dict(route_params),
        "focusMode": focus_mode,
        "routeExact": bool(todo.get("routeExact")),
    }


def project_teacher_todo(todo: dict | None) -> dict | None:
    """Return the T1 Teacher Todo contract from an existing workbench Todo DTO.

    No lookup is performed here.  In particular this function contains no mapping
    keyed by ``todoType`` and never inspects title/group text to choose a page.
    """
    if not todo:
        return None

    source_biz_type = _clean(todo.get("sourceBizType")) or _clean(todo.get("bizType"))
    source_biz_id = _clean(todo.get("sourceBizId")) or _clean(todo.get("bizId")) or _clean(todo.get("recordId"))
    record_id = _clean(todo.get("recordId")) or source_biz_id
    allowed_actions = todo.get("allowedActions") if isinstance(todo.get("allowedActions"), list) else []
    target = _resolved_target(todo)

    # Before Student V3 T8 handoff, actionKey may not yet exist in the legacy
    # workbench DTO.  routeName is already server-authoritative, so it is a safe
    # compatibility identifier; it is never derived from todoType/title.
    action_key = _clean(todo.get("actionKey")) or (_clean(todo.get("routeName")) if target else None)
    action = None
    if target and action_key:
        action = {
            "actionKey": action_key,
            "target": target,
            "allowedActions": list(allowed_actions),
            "expectedVersion": _expected_version(todo),
        }

    return {
        "id": _clean(todo.get("id")) or _clean(todo.get("todoId")),
        "title": _clean(todo.get("title")),
        "todoType": _clean(todo.get("todoType")),
        "sourceModule": _clean(todo.get("sourceModule")),
        "sourceBizType": source_biz_type,
        "sourceBizId": source_biz_id,
        "recordId": record_id,
        "status": _clean(todo.get("status")),
        "deadline": todo.get("deadline", todo.get("dueAt")),
        "priority": _clean(todo.get("priority")),
        "allowedActions": list(allowed_actions),
        "expectedVersion": _expected_version(todo),
        "action": action,
    }


def project_teacher_todos(items: list[dict] | None) -> list[dict]:
    """Project only the current bounded page; this helper never fetches data."""
    return [projected for item in (items or []) if (projected := project_teacher_todo(item)) is not None]
