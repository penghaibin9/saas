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
