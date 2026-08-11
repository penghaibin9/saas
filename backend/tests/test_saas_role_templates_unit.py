"""SaaS 角色模板与身份导入合同。

原有纯单元测试完整保存在同目录 ``_saas_role_templates_contracts.py``；本文件复用所有
未变化的测试，只对已经发生权威架构演进的四个合同做显式更新。这样不删除、不 skip、
不 xfail 任何既有覆盖，同时避免为满足旧静态断言把生产入口退回到师生混合路由。
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


_HELPER = Path(__file__).with_name("_saas_role_templates_contracts.py")
_SPEC = importlib.util.spec_from_file_location("_saas_role_templates_contracts", _HELPER)
assert _SPEC is not None and _SPEC.loader is not None
_LEGACY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LEGACY)

_REPLACED = {
    "test_every_school_permission_role_has_a_versioned_template",
    "test_identity_import_api_has_no_raw_json_account_creation_bypass",
    "test_frontend_exposes_batch_account_creation_only_at_fixed_system_route",
    "test_business_import_screens_show_the_non_account_creation_boundary",
}
for _name in dir(_LEGACY):
    if _name.startswith("test_") and _name not in _REPLACED:
        globals()[_name] = getattr(_LEGACY, _name)


def test_every_school_permission_role_has_a_versioned_template():
    """学校租户角色模板覆盖所有学校角色，但不得混入平台控制面角色。"""
    template_codes = {item["roleCode"] for item in _LEGACY.BUILTIN_ROLE_TEMPLATES}
    school_permission_codes = {
        code for code in _LEGACY.ROLE_PERMISSIONS
        if not code.startswith("PLATFORM_")
    }
    assert school_permission_codes == template_codes
    assert not any(code.startswith("PLATFORM_") for code in template_codes)


def test_identity_import_api_has_no_raw_json_account_creation_bypass():
    """允许通用 xlsx + 师生专用 xlsx 工作流，但禁止出现 raw JSON 建号旁路。"""
    root = Path(__file__).resolve().parents[2]
    system_api = root / "backend/app/api/v1/system.py"
    tree = ast.parse(system_api.read_text(encoding="utf-8"))
    routes = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            route = decorator.args[0].value
            if isinstance(route, str) and route.startswith("/system/identity-import"):
                routes.add((decorator.func.attr.upper(), route))

    assert routes == {
        ("GET", "/system/identity-import/role-templates"),
        ("GET", "/system/identity-import/template"),
        ("POST", "/system/identity-import/validate-file"),
        ("POST", "/system/identity-import/confirm-batch"),
        ("GET", "/system/identity-import/students/template"),
        ("POST", "/system/identity-import/students/validate-file"),
        ("POST", "/system/identity-import/students/confirm-batch"),
        ("GET", "/system/identity-import/teachers/template"),
        ("POST", "/system/identity-import/teachers/validate-file"),
        ("POST", "/system/identity-import/teachers/confirm-batch"),
        ("GET", "/system/identity-import/batches/{batch_no}/errors"),
    }
    assert all(
        path.endswith(("/template", "/validate-file", "/confirm-batch", "/errors", "/role-templates"))
        or "/batches/" in path
        for _method, path in routes
    )


def test_frontend_exposes_batch_account_creation_only_at_fixed_system_route():
    root = Path(__file__).resolve().parents[2]
    dashboard = (root / "frontend/src/modules/system/views/SystemDashboardView.vue").read_text(
        encoding="utf-8")
    users = (root / "frontend/src/modules/system/views/SystemUserListView.vue").read_text(
        encoding="utf-8")
    routes = (root / "frontend/src/modules/system/system.routes.js").read_text(encoding="utf-8")

    assert "this.$router.push('/admin/system/identity-import/students')" in dashboard
    assert "'/admin/system/identity-import/students'" in users
    assert "'/admin/system/identity-import/teachers'" in users
    assert "path: 'identity-import/students'" in routes
    assert "path: 'identity-import/teachers'" in routes
    # 老入口只允许兼容跳转，不能重新变回师生混合建号页面。
    assert "path: 'identity-import'" in routes
    assert "redirect: '/admin/system/identity-import/students'" in routes
    assert "query: { action: 'create' }" not in users
    assert "/admin/system/users/account-import" not in dashboard
    assert "/admin/system/users/account-import" not in users


def test_business_import_screens_show_the_non_account_creation_boundary():
    root = Path(__file__).resolve().parents[2]
    notice = (root / "frontend/src/components/common/AccountImportBoundaryNotice.vue").read_text(
        encoding="utf-8")
    assert "此处不会创建登录账号" in notice
    assert 'to="/admin/system/identity-import/students"' in notice

    direct_notice_files = [
        "frontend/src/views/admin/student/StudentImportExportView.vue",
        "frontend/src/modules/academicAffairs/components/ImportDrawer.vue",
        "frontend/src/modules/campusService/components/ImportDrawer.vue",
        "frontend/src/modules/orientation/components/ImportDialog.vue",
        "frontend/src/modules/employment/components/ImportDialog.vue",
    ]
    for relative in direct_notice_files:
        assert "AccountImportBoundaryNotice" in (root / relative).read_text(encoding="utf-8")

    guarded_excel_imports = [
        "frontend/src/modules/graduation/views/GraduationStudentListView.vue",
        "frontend/src/modules/graduation/views/GraduationMentorListView.vue",
        "frontend/src/modules/internship/views/InternshipStudentListView.vue",
        "frontend/src/modules/internship/views/InternshipMatchListView.vue",
    ]
    for relative in guarded_excel_imports:
        assert "show-account-boundary" in (root / relative).read_text(encoding="utf-8")
