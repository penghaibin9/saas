from pathlib import Path
from app.api.router import build_teacher_mobile_router
from app.api.v1.standalone_mobile_auth import router as mobile_auth_router

ROOT = Path(__file__).resolve().parents[2]
def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_tm02_tm12_teacher_workbench_routes_are_mounted():
    paths={route.path for route in build_teacher_mobile_router().routes}
    assert "/teacher-mobile/internship/workbench/messages" in paths
    assert "/teacher-mobile/internship/workbench/messages/{message_id}/read" in paths
    assert "/teacher-mobile/internship/workbench/todos" in paths

def test_tm16_mobile_auth_exposes_real_switch_role_route():
    assert "/auth/switch-role" in {route.path for route in mobile_auth_router.routes}

def test_tm02_tm12_mobile_surfaces_are_real_api_driven():
    home=_read("mobile/src/pages/teacher-internship/index.vue")
    todos=_read("mobile/src/pages/teacher-internship/todos/index.vue")
    messages=_read("mobile/src/pages/teacher-internship/messages/index.vue")
    api=_read("mobile/src/services/teacherApi.js")
    assert "分类待办" in home and "站内信" in home
    assert "getInternshipWorkbenchTodos" in todos
    assert "getInternshipWorkbenchMessages" in messages
    assert "/teacher-mobile/internship/workbench/todos" in api
    assert "/teacher-mobile/internship/workbench/messages" in api
    assert "不提供脱离业务事实的直接完成按钮" in todos

def test_tm16_mobile_surface_rotates_tokens_and_reloads_internship_context():
    home=_read("mobile/src/pages/teacher-internship/index.vue")
    page=_read("mobile/src/pages/teacher-internship/role-switch/index.vue")
    auth=_read("mobile/src/services/mobileAuth.js")
    assert "切换身份" in home
    assert "switchMobileRole" in page
    assert "commitNewSessionTokens" in auth
    assert "uni.removeStorageSync('gx_internship_context_v1')" in auth
    assert "同一账号" in page


def test_tm12_business_submission_and_resolution_feed_unified_todo():
    helper=_read("backend/app/modules/internship/services/internship_todo_helper.py")
    makeup=_read("backend/app/modules/internship/services/internship_makeup_service.py")
    change=_read("backend/app/modules/internship/services/internship_change_service.py")
    exemption=_read("backend/app/modules/internship/services/internship_checkin_exemption_service.py")
    application=_read("backend/app/modules/internship/services/internship_application_service.py")
    reports=_read("backend/app/modules/internship/services/internship_student_report_context_service.py")
    review=_read("backend/app/modules/internship/services/internship_process_report_service.py")
    for token in (
        "INTERN_MAKEUP_APPROVAL","INTERN_CHANGE_APPROVAL","INTERN_ENTERPRISE_CHANGE",
        "INTERN_EXEMPTION_APPROVAL","INTERN_APPLICATION_REVIEW","INTERN_EXEMPTION_APPLICATION",
        "INTERN_DAILY_REVIEW","INTERN_MONTHLY_REVIEW","INTERN_SUMMARY_REVIEW",
    ):
        assert token in helper
    assert "push_makeup_todo" in makeup and "TODO_MAKEUP" in makeup
    assert "push_change_todo" in change and "change_todo_type" in change
    assert "push_checkin_exemption_todo" in exemption and "TODO_CHECKIN_EXEMPTION" in exemption
    assert "push_application_todo" in application and "application_todo_type" in application
    assert "push_process_report_todo" in reports
    assert "process_report_todo_type" in review and "todo_done" in review


def test_tm02_message_aliases_and_mobile_status_tags_remain_readable():
    backend=_read("backend/app/api/v1/teacher_mobile_workbench.py")
    role=_read("mobile/src/pages/teacher-internship/role-switch/index.vue")
    todos=_read("mobile/src/pages/teacher-internship/todos/index.vue")
    messages=_read("mobile/src/pages/teacher-internship/messages/index.vue")
    assert '"TODO_NOTICE","TODO","REMINDER"' in backend
    assert '"ANNOUNCEMENT","NOTICE"' in backend
    assert 'label="当前身份"' in role
    assert ':status="row.status"' in todos
    assert 'status="UNREAD" label="未读"' in messages
