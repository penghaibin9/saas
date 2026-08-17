"""SaaS 角色模板与身份导入合同。

原有纯单元测试完整保存在同目录 ``_saas_role_templates_contracts.py``；本文件复用所有
未变化的测试，只对已经发生权威架构演进的合同做显式更新。这样不删除、不 skip、
不 xfail 任何既有覆盖，同时避免为满足旧静态断言把生产入口退回到历史架构。
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
    "test_all_production_login_account_constructors_match_the_frozen_allowlist",
    "test_identity_import_api_has_no_raw_json_account_creation_bypass",
    "test_frontend_exposes_batch_account_creation_only_at_fixed_system_route",
    "test_business_import_screens_show_the_non_account_creation_boundary",
}
for _name in dir(_LEGACY):
    if _name.startswith("test_") and _name not in _REPLACED:
        globals()[_name] = getattr(_LEGACY, _name)


def test_every_school_permission_role_has_a_versioned_template():
    """学校租户权限角色必须进入版本化模板目录；平台控制面角色严禁混入。"""
    template_codes = {item["roleCode"] for item in _LEGACY.BUILTIN_ROLE_TEMPLATES}
    school_permission_codes = {
        code for code in _LEGACY.ROLE_PERMISSIONS
        if not code.startswith("PLATFORM_")
    }
    assert school_permission_codes == template_codes
    assert not any(code.startswith("PLATFORM_") for code in template_codes)


def test_all_production_login_account_constructors_match_the_frozen_allowlist():
    """V3 adds exactly one external-enterprise pre-provisioning constructor, not a generic bypass."""
    assert _LEGACY._user_constructor_sites() == {
        ("services/school_onboarding_service.py", "run_onboarding"),
        ("services/platform_service.py", "create_school_admin"),
        ("services/sandbox_service.py", "seed_sandbox"),
        (
            "modules/internship/services/internship_enterprise_auth_service.py",
            "_ensure_invited_user_in_tx",
        ),
    }


def test_enterprise_invite_user_constructor_is_disabled_scoped_preprovision_only():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/internship/services/internship_enterprise_auth_service.py").read_text(
        encoding="utf-8")
    block = source.split("def _ensure_invited_user_in_tx", 1)[1].split("def issue_company_invite", 1)[0]
    assert 'user_type="ENTERPRISE_MENTOR"' in block
    assert 'status="DISABLED"' in block
    assert 'password_hash=hash_password(secrets.token_urlsafe(48))' in block
    assert 'phone_encrypted=encrypt_sensitive(phone_text, "phone")' in block
    assert 'phone_hash=phone_hash' in block
    assert 'must_change_password=False' in block
    assert "db.commit()" not in block
    assert "db.flush()" in block


def test_identity_import_api_has_no_raw_json_account_creation_bypass():
    """身份导入兼容层只允许文件/任务适配，不得出现 raw JSON 建号旁路。"""
    root = Path(__file__).resolve().parents[2]
    compat_api = root / "backend/app/modules/system_admin/routers/identity_import_compat_router.py"
    source = compat_api.read_text(encoding="utf-8")
    tree = ast.parse(source)
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
        ("POST", "/system/identity-import/validate-file"),
        ("POST", "/system/identity-import/students/validate-file"),
        ("POST", "/system/identity-import/students/confirm-batch"),
        ("POST", "/system/identity-import/teachers/validate-file"),
        ("POST", "/system/identity-import/teachers/confirm-batch"),
        ("POST", "/system/identity-import/confirm-batch"),
    }
    assert "LEGACY_IDENTITY_IMPORT_RETIRED" in source
    assert "data_exchange_router.run_identity_import_upload" in source
    assert "confirm_identity_import_job" in source
    assert "User(" not in source
    assert "db.add(" not in source


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
    assert "path: 'identity-import'" in routes
    assert "redirect: '/admin/system/identity-import/students'" in routes
    assert "query: { action: 'create' }" not in users
    assert "/admin/system/users/account-import" not in dashboard
    assert "/admin/system/users/account-import" not in users


def test_business_import_screens_show_the_non_account_creation_boundary():
    root = Path(__file__).resolve().parents[2]
    notice = (root / "frontend/src/components/common/AccountImportBoundaryNotice.vue").read_text(
        encoding="utf-8")
    generic_excel = (root / "frontend/src/components/common/excel/AppExcelImportDrawer.vue").read_text(
        encoding="utf-8")
    assert "此处不会创建登录账号" in notice
    assert 'to="/admin/system/identity-import/students"' in notice
    assert "AccountImportBoundaryNotice" in generic_excel

    direct_notice_files = [
        "frontend/src/views/admin/student/StudentImportExportView.vue",
        "frontend/src/modules/academicAffairs/components/ImportDrawer.vue",
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
