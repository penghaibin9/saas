from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "app/services/affairs_teacher_workbench_guard.py").read_text(
    encoding="utf-8"
)


def test_teacher_affairs_workbench_reuses_strict_visibility():
    assert "from app.services.workbench_todo_service import _visibility_cond" in SOURCE
    assert "visibility = _visibility_cond(db, user)" in SOURCE
    assert 'UnifiedTodo.source_module == "student-affairs"' in SOURCE
    assert "UnifiedTodo.status == \"PENDING\"" in SOURCE
    # 禁止重新引入学院角色直接放行全部池待办的旧条件。
    assert "UnifiedTodo.assignee_id == 0" not in SOURCE


def test_teacher_affairs_workbench_returns_actionable_rows():
    for field in (
        '"todoId"', '"todoType"', '"studentName"', '"studentNo"',
        '"className"', '"recordId"', '"dueAt"', '"overdue"',
        '"allowedActions": ["OPEN"]', '"actionParams"',
    ):
        assert field in SOURCE
    assert '"contractVersion": "AFFAIRS_TEACHER_TODO_V1"' in SOURCE
