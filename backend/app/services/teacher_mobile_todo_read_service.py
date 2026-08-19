"""Teacher Miniapp V3 T1 canonical Todo read facade.

This service intentionally adds no route table and no second Todo storage. It delegates
visibility, pagination and typed target resolution to ``workbench_todo_service`` and only
projects the current bounded page into the Teacher V3 DTO shape.

The shared ``todo_route_registry`` / MobileAction authority remains the sole route source.
Until Student V3 handoff provides a proven teacherMini target, ``action`` stays ``None``.
"""
from __future__ import annotations

from app.services import mobile_teacher_service as teacher_guard
from app.services import workbench_todo_service as todo_svc
from app.services.teacher_mobile_todo_projection_service import (
    project_teacher_todo,
    project_teacher_todos,
)


def list_page(
    user: dict,
    *,
    status: str | None = None,
    todo_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Read one bounded canonical Todo page for the teacher miniapp."""
    teacher_guard._require_teacher(user)
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    rows, total = todo_svc.list_todos(
        user,
        status=status,
        todo_type=todo_type,
        page=page,
        page_size=page_size,
        client="teacherMini",
    )
    items = project_teacher_todos(rows)
    return {
        "items": items,
        "total": int(total or 0),
        "page": page,
        "pageSize": page_size,
        "hasMore": page * page_size < int(total or 0),
    }


def get_one(user: dict, todo_id: str) -> dict | None:
    """Read one canonical Todo while preserving visibility fail-closed semantics."""
    teacher_guard._require_teacher(user)
    row = todo_svc.get_todo(user, todo_id, client="teacherMini")
    return project_teacher_todo(row) if row else None
