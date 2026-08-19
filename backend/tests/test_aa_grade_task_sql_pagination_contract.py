from pathlib import Path


SERVICE = (
    Path(__file__).resolve().parents[1]
    / "app/modules/academic_affairs/services/academic_affairs_grade_service.py"
)


def _list_tasks_source() -> str:
    source = SERVICE.read_text(encoding="utf-8")
    start = source.index("def list_tasks(")
    end = source.index("\n\ndef roster(", start)
    return source[start:end]


def test_grade_task_list_executes_count_and_page_in_sql():
    source = _list_tasks_source()

    assert "select(func.count()).select_from(AaGradeTask).where(*conditions)" in source
    assert ".order_by(AaGradeTask.id.desc())" in source
    assert ".offset(offset)" in source
    assert ".limit(limit)" in source
    assert "return [_task_row(row) for row in rows], total" in source


def test_grade_task_list_does_not_materialize_all_rows_before_paging():
    source = _list_tasks_source()

    assert "items = [_task_row(row) for row in rows]" not in source
    assert "items[start:start + int(page_size)]" not in source
    assert "len(items)" not in source
