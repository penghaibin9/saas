"""Teacher Miniapp V3 workbench projection.

T8 closes the object-action gap without creating another Todo authority.  The
canonical workbench snapshot still owns visibility/counts and the canonical
Todo registry still owns targets.  This layer only shapes the already-loaded
snapshot for the mobile workbench and asks the snapshot for ``teacherMini``
projection so dueSoon keeps the same typed action as the Todo page.
"""
from __future__ import annotations

from app.services import mobile_performance_service as perf
from app.services import workbench_snapshot_service as snapshot_svc


def teacher_workbench(user: dict, page_size: int = 8) -> dict:
    current = perf._require_teacher(user)
    size = max(1, min(20, int(page_size or 8)))

    # One authoritative snapshot session for Todo summary/count/items.  Passing
    # teacherMini is critical: _todo_dict then resolves the single shared
    # todo_route_registry and T1 projects the MobileAction.  No per-row lookup.
    snapshot = snapshot_svc.snapshot(current, page_size=size, client="teacherMini")
    risk = perf.teacher_risk_students_page(current, "all", 1, 5)

    summary = snapshot.get("summary") or {}
    count = snapshot.get("count") or {}
    todos = snapshot.get("todos") or {}
    by_type = count.get("byType") or {}

    metrics = [
        {"key": "pending", "label": "待我处理", "value": int(summary.get("pending") or 0)},
        {"key": "overdue", "label": "已逾期", "value": int(summary.get("overdue") or 0)},
        {"key": "near", "label": "24h到期", "value": int(summary.get("nearDeadline") or 0)},
        {"key": "done", "label": "今日完成", "value": int(summary.get("doneToday") or 0)},
    ]

    due = []
    for item in (todos.get("items") or [])[:5]:
        # Keep canonical identity/route/action fields intact. UI aliases are
        # additive only; group/todoType never determines navigation here.
        due.append({
            **item,
            "id": item.get("todoId") or item.get("id"),
            "module": item.get("sourceModule") or item.get("todoType") or "",
            "student": item.get("studentName") or "",
            "deadline": item.get("dueAt") or item.get("deadline") or "",
            "status": item.get("status") or "PENDING",
        })

    return {
        "contextTitle": summary.get("role") or current.get("currentRoleCode") or "",
        "metrics": metrics,
        "pendingTotal": int(summary.get("pending") or 0),
        "dueSoon": due,
        "riskStudents": risk.get("list") or [],
        "recent": [],
        "messageSummary": snapshot.get("messages") or {},
        "_real": True,
        "_role": summary.get("role") or current.get("currentRoleCode") or "",
        "_byType": by_type,
        "partialFailures": {"count": False, "todos": False, "risk": False},
    }
