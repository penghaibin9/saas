"""Teacher Miniapp V3 canonical Todo read facade.

T1 keeps the frozen page/offset contract for existing consumers.  T2 adds a dedicated
continuous keyset reader without changing that legacy surface.  Neither path owns a route
table: visibility and typed target resolution stay in ``workbench_todo_service`` and the
shared MobileAction authority.
"""
from __future__ import annotations

from app.services import mobile_teacher_service as teacher_guard
from app.services import teacher_mobile_todo_keyset_service as keyset_svc
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
    """Read one bounded canonical Todo page for the teacher miniapp (T1 compatibility)."""
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


def list_continuous(
    user: dict,
    *,
    status: str | None = None,
    todo_type: str | None = None,
    cursor: str | None = None,
    page_size: int = 20,
) -> dict:
    """T2 continuous list: true seek pagination, first-page counts, no repeated COUNT."""
    teacher_guard._require_teacher(user)
    data = keyset_svc.list_continuous(
        user,
        status=status,
        todo_type=todo_type,
        cursor=cursor,
        page_size=page_size,
    )
    return {**data, "items": project_teacher_todos(data.get("items") or [])}


def get_one(user: dict, todo_id: str) -> dict | None:
    """Read one canonical Todo while preserving visibility fail-closed semantics."""
    teacher_guard._require_teacher(user)
    row = todo_svc.get_todo(user, todo_id, client="teacherMini")
    return project_teacher_todo(row) if row else None
