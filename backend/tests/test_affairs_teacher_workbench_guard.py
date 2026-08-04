from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = (ROOT / "backend/app/services/affairs_teacher_workbench_service.py").read_text(encoding="utf-8")
GUARD = (ROOT / "backend/app/services/affairs_teacher_workbench_guard.py").read_text(encoding="utf-8")
ROUTE = (ROOT / "backend/app/api/v1/mobile.py").read_text(encoding="utf-8")


def test_teacher_workbench_uses_one_strict_visibility_condition_for_count_cards_and_page():
    assert "from app.services.workbench_todo_service import _visibility_cond" in SERVICE
    assert "visibility = _visibility_cond(db, user)" in SERVICE
    assert 'UnifiedTodo.source_module == "student-affairs"' in SERVICE
    assert 'UnifiedTodo.status == "PENDING"' in SERVICE
    assert "select(func.count()).select_from(UnifiedTodo).where(*conds)" in SERVICE
    assert ".group_by(UnifiedTodo.todo_type)" in SERVICE
    assert ".offset((page - 1) * page_size)" in SERVICE
    assert ".limit(page_size)" in SERVICE
    assert ".limit(100)" not in SERVICE
    assert '"total": total' in SERVICE
    assert '"hasMore": page * page_size < total' in SERVICE


def test_teacher_workbench_is_explicit_service_not_runtime_patch():
    assert "mobile_affairs_service.teacher_affairs =" not in GUARD
    assert "def install() -> None" in GUARD
    assert "query_workbench(user, page=page, page_size=pageSize)" in ROUTE
    assert '"contractVersion": CONTRACT_VERSION' in SERVICE
    assert 'CONTRACT_VERSION = "AFFAIRS_TEACHER_TODO_V2"' in SERVICE
