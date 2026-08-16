"""C-W1：管理员特殊补录不得污染正式课堂旷课预警。"""


def test_formal_attendance_warning_condition_excludes_admin_special():
    from app.models import AaAttendanceSession
    from app.modules.academic_affairs.services import academic_affairs_warning_service as service

    condition = service._formal_attendance_session_condition(AaAttendanceSession)
    sql = str(condition.compile(compile_kwargs={"literal_binds": True}))
    assert "source_type" in sql
    assert "IS NULL" in sql
    assert "ADMIN_SPECIAL" in sql
    assert "FORMAL_TEACHING" in sql
    assert "!=" in sql


def test_attendance_warning_scan_source_contract_is_formal_only():
    from pathlib import Path

    source = Path(
        "app/modules/academic_affairs/services/academic_affairs_warning_service.py"
    ).read_text(encoding="utf-8")
    start = source.index("def scan_attendance_warnings")
    end = source.index("# ═══════════ 列表 / 看板 / 统计", start)
    body = source[start:end]
    assert "_formal_attendance_session_condition(AaAttendanceSession)" in body
    assert "FORMAL_TEACHING" in body
