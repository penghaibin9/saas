from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re


def _load_base():
    script = Path(__file__).with_name("student_affairs_leave_cutover.py")
    spec = spec_from_file_location("student_affairs_leave_cutover", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载施工脚本：{script}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_base()


def patch_remaining_callers() -> None:
    for path in Path("student-portal/src").rglob("*.vue"):
        text = path.read_text(encoding="utf-8")
        updated = re.sub(
            r"portalApi\.affairsServiceApply\(\{\s*serviceKey:\s*['\"]LEAVE['\"]\s*,\s*(.*?)\}\)",
            r"portalApi.affairsLeaveApply({\1})",
            text,
            flags=re.S,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")

    for path in Path("miniapp/src").rglob("*.vue"):
        text = path.read_text(encoding="utf-8")
        updated = re.sub(
            r"studentApi\.submitServiceApply\(\{\s*serviceKey:\s*['\"]LEAVE['\"]\s*,\s*(.*?)\}\)",
            r"studentApi.applyLeave({\1})",
            text,
            flags=re.S,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def first_cut_rerunnable() -> None:
    campus_api = Path("backend/app/api/v1/campus_service.py").read_text(encoding="utf-8")
    campus_service = Path("backend/app/services/campus_service_service.py").read_text(encoding="utf-8")
    already_cut = (
        "请假旧接口已退出" in campus_api
        and "请假旧实现已退出" in campus_service
    )
    if not already_cut:
        base.first_cut()
    patch_remaining_callers()


def patch_route_ownership() -> None:
    campus_path = Path("frontend/src/modules/campusService/campusService.routes.js")
    campus = campus_path.read_text(encoding="utf-8")
    campus = re.sub(
        r"\n    \{\n      path: '/admin/student-affairs/leave',.*?\n    \},\n    \{\n      path: '',",
        "\n    {\n      path: '',",
        campus,
        count=1,
        flags=re.S,
    )
    if "path: '/admin/student-affairs/leave'" in campus:
        raise RuntimeError("formal leave routes still owned by campusServiceRoutes")
    campus_path.write_text(campus, encoding="utf-8")

    sa_path = Path("frontend/src/modules/studentAffairs/studentAffairs.routes.js")
    sa = sa_path.read_text(encoding="utf-8")
    if "name: 'student-affairs-leave'" not in sa:
        anchor = """      {
        /* 旧「辅导员工作台」双首页 → 统一角色化工作台 /（WorkbenchView） */
"""
        block = """      {
        path: 'leave',
        name: 'student-affairs-leave',
        component: () => import('@/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假审批' }
      },
      {
        path: 'leave/followup',
        name: 'student-affairs-leave-followup',
        component: () => import('@/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '销假与续假' }
      },
      {
        path: 'leave/ledger',
        name: 'student-affairs-leave-ledger',
        component: () => import('@/modules/studentAffairs/views/leave/LeaveLedgerView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假台账' }
      },
      {
        path: 'leave/stats',
        name: 'student-affairs-leave-stats',
        component: () => import('@/modules/studentAffairs/views/leave/LeaveStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假统计' }
      },
"""
        if anchor not in sa:
            raise RuntimeError("student affairs route insertion anchor missing")
        sa = sa.replace(anchor, block + anchor, 1)
    sa = sa.replace(
        " * 班级/请假已由 master 正式模块承接（/admin/campus-service/classes、/leave 系列），此处不重复。",
        " * 班级旧入口仍兼容；请假正式路由已迁入本 STUDENT_AFFAIRS 路由树。",
    )
    sa_path.write_text(sa, encoding="utf-8")


def block_generic_leave_entrypoints() -> None:
    mobile_path = Path("backend/app/api/v1/mobile.py")
    mobile = mobile_path.read_text(encoding="utf-8")
    old = '''@router.post("/campus-service/apply", summary="提交在校服务申请（本人）")
def campus_service_apply(body: dict = Body(...), user=Depends(get_current_user)):
    return success(stu.campus_service_apply(user, body))
'''
    new = '''@router.post("/campus-service/apply", summary="提交在校服务申请（本人，不含请假）")
def campus_service_apply(body: dict = Body(...), user=Depends(get_current_user)):
    if str((body or {}).get("serviceKey") or "").strip().upper() == "LEAVE":
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "请假已迁移到 /mobile/affairs/leave 专用入口")
    return success(stu.campus_service_apply(user, body))
'''
    if old in mobile:
        mobile = mobile.replace(old, new, 1)
    elif new not in mobile:
        raise RuntimeError("mobile generic service entry anchor missing")
    mobile_path.write_text(mobile, encoding="utf-8")

    portal_path = Path("backend/app/student_portal/router.py")
    portal = portal_path.read_text(encoding="utf-8")
    old = '''@router.post("/affairs/service-apply", summary="通用学工事务申请（请假/咨询/工单，本人）")
def affairs_service_apply(user=Depends(get_current_user), body: dict = Body(...)):
    return success(affairs.service_apply(user, body))
'''
    new = '''@router.post("/affairs/service-apply", summary="通用学工事务申请（咨询/工单，本人；不含请假）")
def affairs_service_apply(user=Depends(get_current_user), body: dict = Body(...)):
    if str((body or {}).get("serviceKey") or "").strip().upper() == "LEAVE":
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "请假已迁移到 /portal/affairs/leave 专用入口")
    return success(affairs.service_apply(user, body))
'''
    if old in portal:
        portal = portal.replace(old, new, 1)
    elif new not in portal:
        raise RuntimeError("portal generic service entry anchor missing")
    portal_path.write_text(portal, encoding="utf-8")

    service_path = Path("backend/app/student_portal/services/affairs_service.py")
    service = service_path.read_text(encoding="utf-8")
    old = '''def service_apply(user: dict, body: dict) -> dict:
    """通用学工事务申请（请假/咨询/工单，复用现有学生写入口 campus_service_apply）。"""
    return stu.campus_service_apply(user, body or {})
'''
    new = '''def service_apply(user: dict, body: dict) -> dict:
    """通用咨询/工单入口；请假必须走 affairs_leave_service 专用状态机。"""
    body = body or {}
    if str(body.get("serviceKey") or "").strip().upper() == "LEAVE":
        raise AppException("VALIDATION_ERROR", "请假已迁移到专用入口")
    return stu.campus_service_apply(user, body)
'''
    if old in service:
        service = service.replace(old, new, 1)
    elif new not in service:
        raise RuntimeError("portal generic service implementation anchor missing")
    service = service.replace(
        "学工学生自视图已在 mobile_affairs_service（aff：leave_my/funding_my/aid_my/discipline_my/\noverview_my，均经 aff._me 收口本人+非学生403）。学生写入口为 campus_service_apply（通用事务申请：\n请假/咨询/工单）。本刀 PC 接出：学工自视图聚合 + 通用事务申请 + 打印回执/请假条。",
        "学工学生自视图已在 mobile_affairs_service（aff：leave_my/funding_my/aid_my/discipline_my/\noverview_my，均经 aff._me 收口本人+非学生403）。请假使用专用 affairs_leave_service；\ncampus_service_apply 仅保留咨询/工单。本刀 PC 接出学工自视图聚合、专用请假和打印回执。",
    )
    service_path.write_text(service, encoding="utf-8")


def absorb_leave_runtime_contract() -> None:
    mobile_path = Path("backend/app/services/mobile_affairs_service.py")
    mobile = mobile_path.read_text(encoding="utf-8")
    if "from app.services import affairs_leave_service as leave_svc" not in mobile:
        mobile = mobile.replace(
            "    from app.models import CsLeave, CsServiceStudent\n",
            "    from app.models import CsLeave, CsServiceStudent\n    from app.services import affairs_leave_service as leave_svc\n",
            1,
        )
    mobile = re.sub(
        r"    L = \{\"DRAFT\": \"草稿\".*?\n         \"OVERDUE\": \"逾期未销假\", \"CANCELLED\": \"已取消\"\}\n",
        '    L = {**leave_svc.L_AFF, "PENDING_REVIEW": "待审批"}\n',
        mobile,
        count=1,
        flags=re.S,
    )
    if "actions = leave_svc._allowed_actions(x.affairs_status)" not in mobile:
        mobile = mobile.replace(
            "        for x in rows:\n            st = x.affairs_status or x.status\n            items.append({\n",
            "        for x in rows:\n            st = x.affairs_status or x.status\n            actions = leave_svc._allowed_actions(x.affairs_status)\n            items.append({\n",
            1,
        )
    mobile = re.sub(
        r'                "allowedActions": \(actions := \(\n.*?\n                \)\),\n',
        '                "allowedActions": actions,\n',
        mobile,
        count=1,
        flags=re.S,
    )
    if "actions = leave_svc._allowed_actions(x.affairs_status)" not in mobile:
        raise RuntimeError("mobile leave actions were not moved to formal leave service")
    mobile_path.write_text(mobile, encoding="utf-8")

    contract_path = Path("backend/app/services/affairs_four_end_contract.py")
    contract = contract_path.read_text(encoding="utf-8")
    contract = contract.replace("- 学生请假自视图返回 version/allowedActions；\n", "")
    contract = contract.replace(
        '        "affairs_leave_service", "affairs_aid_service", "affairs_funding_service",\n',
        '        "affairs_aid_service", "affairs_funding_service",\n',
        1,
    )
    optimistic_block = contract.split("def _patch_optimistic_lock() -> None:", 1)[1].split(
        "def _teacher_permissions", 1
    )[0]
    if "affairs_leave_service" in optimistic_block:
        raise RuntimeError("leave service remains in optimistic-lock monkey patch")
    contract_path.write_text(contract, encoding="utf-8")


def write_cutover_contract_test() -> None:
    test_path = Path("backend/tests/test_affairs_leave_cutover_contract.py")
    test_path.write_text(
        '''from pathlib import Path\n\n\nROOT = Path(__file__).resolve().parents[2]\n\n\ndef read(path: str) -> str:\n    return (ROOT / path).read_text(encoding="utf-8")\n\n\ndef test_legacy_leave_routes_and_fake_test_adapters_are_gone():\n    assert "/campus-service/leaves" not in read("backend/app/api/v1/campus_service.py")\n    assert "请假旧接口已退出" in read("backend/app/api/v1/campus_service.py")\n    for path in (\n        "backend/affairs_test_compat.py",\n        "backend/affairs_test_diagnostics.py",\n        "backend/affairs_test_legacy_inputs.py",\n    ):\n        assert not (ROOT / path).exists()\n    assert "affairs_test_" not in read("backend/pytest.ini")\n\n\ndef test_dedicated_self_leave_endpoints_and_callers_are_single_source():\n    api = read("backend/app/api/v1/affairs_leave_self_api.py")\n    assert '@router.post("/portal/affairs/leave"' in api\n    assert '@router.post("/mobile/affairs/leave"' in api\n    assert "leave_svc.apply_leave" in api\n    portal = read("student-portal/src/services/portalApi.js")\n    mini = read("miniapp/src/services/realApi.js")\n    assert "request('/portal/affairs/leave', { method: 'POST', body })" in portal\n    assert "realRequest('/mobile/affairs/leave', { method: 'POST', data: body || {} })" in mini\n    for root in ("student-portal/src", "miniapp/src"):\n        for file in (ROOT / root).rglob("*"):\n            if file.is_file() and file.suffix in {".js", ".vue", ".ts"}:\n                assert "serviceKey: 'LEAVE'" not in file.read_text(encoding="utf-8", errors="ignore")\n\n\ndef test_generic_service_entrypoints_reject_leave():\n    mobile = read("backend/app/api/v1/mobile.py")\n    portal = read("backend/app/student_portal/router.py")\n    service = read("backend/app/student_portal/services/affairs_service.py")\n    assert "请假已迁移到 /mobile/affairs/leave 专用入口" in mobile\n    assert "请假已迁移到 /portal/affairs/leave 专用入口" in portal\n    assert "请假已迁移到专用入口" in service\n\n\ndef test_formal_management_routes_belong_to_student_affairs_tree():\n    student_routes = read("frontend/src/modules/studentAffairs/studentAffairs.routes.js")\n    campus_routes = read("frontend/src/modules/campusService/campusService.routes.js")\n    for path in ("leave", "leave/followup", "leave/ledger", "leave/stats"):\n        assert f"path: '{path}'" in student_routes\n    assert "LeaveApprovalWorkbenchView.vue" in student_routes\n    assert "path: '/admin/student-affairs/leave'" not in campus_routes\n    assert "redirect: '/admin/student-affairs/leave'" in campus_routes\n\n\ndef test_leave_version_and_allowed_actions_are_formal_not_monkey_patched():\n    leave_service = read("backend/app/services/affairs_leave_service.py")\n    mobile_service = read("backend/app/services/mobile_affairs_service.py")\n    contract = read("backend/app/services/affairs_four_end_contract.py")\n    assert '"version": int(x.version or 0)' in leave_service\n    assert '"allowedActions": _allowed_actions(x.affairs_status)' in leave_service\n    assert "actions = leave_svc._allowed_actions(x.affairs_status)" in mobile_service\n    optimistic = contract.split("def _patch_optimistic_lock() -> None:", 1)[1].split(\n        "def _teacher_permissions", 1\n    )[0]\n    assert "affairs_leave_service" not in optimistic\n''',
        encoding="utf-8",
    )


def audit_versions() -> None:
    mobile = Path("backend/app/services/mobile_affairs_service.py").read_text(encoding="utf-8")
    if "actions = leave_svc._allowed_actions(x.affairs_status)" not in mobile:
        raise RuntimeError("mobile leave allowedActions is not sourced from formal service")

    campus = Path("frontend/src/modules/campusService/campusService.routes.js").read_text(encoding="utf-8")
    student = Path("frontend/src/modules/studentAffairs/studentAffairs.routes.js").read_text(encoding="utf-8")
    if "path: '/admin/student-affairs/leave'" in campus:
        raise RuntimeError("formal leave route still owned by legacy route file")
    if "name: 'student-affairs-leave'" not in student:
        raise RuntimeError("formal leave route missing from student affairs route tree")

    contract = Path("backend/app/services/affairs_four_end_contract.py").read_text(encoding="utf-8")
    optimistic = contract.split("def _patch_optimistic_lock() -> None:", 1)[1].split(
        "def _teacher_permissions", 1
    )[0]
    if "affairs_leave_service" in optimistic:
        raise RuntimeError("leave service still depends on optimistic-lock monkey patch")

    for path in (
        "backend/app/api/v1/mobile.py",
        "backend/app/student_portal/router.py",
        "backend/app/student_portal/services/affairs_service.py",
    ):
        text = Path(path).read_text(encoding="utf-8")
        if "请假已迁移" not in text:
            raise RuntimeError(f"legacy generic leave entry is not blocked: {path}")


if __name__ == "__main__":
    print("CUTOVER_STAGE first_cut", flush=True)
    first_cut_rerunnable()
    print("CUTOVER_STAGE second_cut", flush=True)
    base.second_cut()
    print("CUTOVER_STAGE third_cut", flush=True)
    base.third_cut()
    patch_route_ownership()
    block_generic_leave_entrypoints()
    absorb_leave_runtime_contract()
    write_cutover_contract_test()
    print("CUTOVER_STAGE audit", flush=True)
    base.audit()
    audit_versions()
    print("leave cutover follow-up audit passed", flush=True)
