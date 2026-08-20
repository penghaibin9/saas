from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_t8_workbench_snapshot_requests_teacher_typed_actions_without_n_plus_one():
    service = _src("backend/app/services/teacher_mobile_workbench_v3_service.py")
    assert 'snapshot_svc.snapshot(current, page_size=size, client="teacherMini")' in service
    assert 'perf.teacher_risk_students_page(current, "all", 1, 5)' in service
    assert '"action"' not in service or 'item.get("action")' not in service
    assert '"dueSoon": due' in service
    assert "for item in (todos.get(\"items\") or [])[:5]" in service
    assert "get_one(" not in service
    assert "list_todos(" not in service


def test_t8_performance_route_uses_typed_workbench_projection():
    route = _src("backend/app/api/v1/mobile_performance.py")
    assert "teacher_mobile_workbench_v3_service as teacher_workbench_v3" in route
    assert "teacher_workbench_v3.teacher_workbench(user, page_size=page_size)" in route
