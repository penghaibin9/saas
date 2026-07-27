from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEGACY_LEAVE_API = "/campus-service/" + "leaves"
LEGACY_SERVICE_KEY = "serviceKey: " + "'LEAVE'"
FAKE_TEST_ADAPTERS = (
    "backend/affairs_test_" + "compat.py",
    "backend/affairs_test_" + "diagnostics.py",
    "backend/affairs_test_" + "legacy_inputs.py",
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_legacy_leave_routes_and_fake_test_adapters_are_gone():
    assert LEGACY_LEAVE_API not in read("backend/app/api/v1/campus_service.py")
    assert "请假旧接口已退出" in read("backend/app/api/v1/campus_service.py")
    for path in FAKE_TEST_ADAPTERS:
        assert not (ROOT / path).exists()
    assert "affairs_test_" not in read("backend/pytest.ini")


def test_dedicated_self_leave_endpoints_and_callers_are_single_source():
    api = read("backend/app/api/v1/affairs_leave_self_api.py")
    assert '@router.post("/portal/affairs/leave"' in api
    assert '@router.post("/mobile/affairs/leave"' in api
    assert "leave_svc.apply_leave" in api
    portal = read("student-portal/src/services/portalApi.js")
    mini = read("miniapp/src/services/realApi.js")
    assert "request('/portal/affairs/leave', { method: 'POST', body })" in portal
    assert "realRequest('/mobile/affairs/leave', { method: 'POST', data: body || {} })" in mini
    for root in ("student-portal/src", "miniapp/src"):
        for file in (ROOT / root).rglob("*"):
            if file.is_file() and file.suffix in {".js", ".vue", ".ts"}:
                assert LEGACY_SERVICE_KEY not in file.read_text(encoding="utf-8", errors="ignore")


def test_generic_service_entrypoints_reject_leave():
    mobile = read("backend/app/api/v1/mobile.py")
    portal = read("backend/app/student_portal/router.py")
    service = read("backend/app/student_portal/services/affairs_service.py")
    assert "请假已迁移到 /mobile/affairs/leave 专用入口" in mobile
    assert "请假已迁移到 /portal/affairs/leave 专用入口" in portal
    assert "请假已迁移到专用入口" in service


def test_formal_management_routes_belong_to_student_affairs_tree():
    student_routes = read("frontend/src/modules/studentAffairs/studentAffairs.routes.js")
    campus_routes = read("frontend/src/modules/campusService/campusService.routes.js")
    for path in ("leave", "leave/followup", "leave/ledger", "leave/stats"):
        assert f"path: '{path}'" in student_routes
    assert "LeaveApprovalWorkbenchView.vue" in student_routes
    assert "path: '/admin/student-affairs/leave'" not in campus_routes
    assert "redirect: '/admin/student-affairs/leave'" in campus_routes


def test_leave_version_and_allowed_actions_are_formal_not_monkey_patched():
    leave_service = read("backend/app/services/affairs_leave_service.py")
    mobile_service = read("backend/app/services/mobile_affairs_service.py")
    contract = read("backend/app/services/affairs_four_end_contract.py")
    assert '"version": int(x.version or 0)' in leave_service
    assert '"allowedActions": _allowed_actions(x.affairs_status)' in leave_service
    assert "actions = leave_svc._allowed_actions(x.affairs_status)" in mobile_service
    optimistic = contract.split("def _patch_optimistic_lock() -> None:", 1)[1].split(
        "def _teacher_permissions", 1
    )[0]
    assert "affairs_leave_service" not in optimistic
