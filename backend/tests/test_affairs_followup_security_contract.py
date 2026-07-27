from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_student_affairs_history_export_requires_full_scope_before_querying_rows():
    source = _read("backend/app/services/domain_export_service.py")

    guard_call = 'if domain == "student-affairs":\n        _require_student_affairs_full_scope(user)'
    assert guard_call in source
    assert 'ctx.scope_type != "TENANT_ALL"' in source
    assert source.index(guard_call) < source.index("items, total = _call_list(list_path)")


def test_student_message_detail_never_routes_students_into_teacher_pages():
    source = _read("miniapp/src/pages/common/message-detail/index.vue")

    assert "/pages/teacher/" not in source
    assert "ACTION_ROUTES" in source
    assert "actionKey" in source
    assert "actionParams" in source
    assert "该消息暂未配置安全的学生端处理入口" in source


def test_student_portal_message_click_reads_action_metadata_and_uses_whitelisted_routes():
    source = _read("student-portal/src/views/messages/MessagesView.vue")

    assert "ACTION_ROUTES" in source
    assert "MODULE_ROUTES" in source
    assert "request(`/mobile/me/messages/${mid}`)" in source
    assert "router.push(messageTarget(detail))" in source
    assert "'student-affairs': '/campus-service'" in source
