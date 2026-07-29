from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_mobile_home_returns_lightweight_message_summary_without_message_content():
    source = _read("app/services/mobile_student_service.py")
    block = source.split("def me_overview", 1)[1].split("def _home_cache_key", 1)[0]
    assert '"messageSummary"' in block
    assert '"emergencyPendingCount"' in block
    assert "notice_columns" in block
    assert "rendered_content_plain" not in block
    assert '"content"' not in block


def test_mobile_home_cache_is_tenant_and_stable_identity_scoped():
    source = _read("app/services/mobile_student_service.py")
    block = source.split("def _home_cache_key", 1)[1].split("def invalidate_home_cache", 1)[0]
    assert "tenantId" in block
    assert "studentId" in block
    assert "userId" in block
    assert "studentNo" not in block.split("return", 1)[1]


def test_mobile_home_observability_does_not_log_sql_or_parameters():
    source = _read("app/services/mobile_student_service.py")
    block = source.split("def home", 1)[1].split("def my_todos", 1)[0]
    assert "query_count=" in block
    assert "duration_ms=" in block
    assert "cache_set_json_if_absent" in block
    assert "random.randint" in block
    assert "statement" not in block
    assert "parameters" not in block


def test_stage_a_routes_are_bounded_and_do_not_touch_file_center():
    routes = _read("app/api/v1/mobile.py")
    assert '"/me/messages-page"' in routes
    assert '"/teacher/todos-page"' in routes
    assert '"/teacher/risk-students-page"' in routes
    assert "le=50" in routes
    assert "file_center" not in routes


def test_teacher_mobile_uses_authoritative_affairs_leave_service():
    source = _read("app/services/mobile_teacher_service.py")
    assert "affairs_leave_service.list_leaves" in source
    assert "campus_service_service.list_leaves" not in source
    assert 'status="PENDING"' in source
