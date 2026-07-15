"""SaaS 角色模板与开局预检纯单元测试；明确不连接数据库。"""
from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.core.exceptions import AppException
from app.core.permissions import ROLE_PERMISSIONS, has_permission
from app.services import school_onboarding_service as onboarding
from app.services import identity_import_service
from app.services.saas_role_templates import (BUILTIN_ROLE_TEMPLATES,
                                               role_catalog,
                                               role_codes_from_row)
from app.services import saas_role_service
from pathlib import Path
import ast


class _Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _FakeDb:
    def __init__(self, scalar_results):
        self.scalar_results = list(scalar_results)
        self.added = []
        self.flush_count = 0

    def scalars(self, statement):
        return _Rows(self.scalar_results.pop(0))

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flush_count += 1


def test_every_school_permission_role_has_a_versioned_template():
    template_codes = {item["roleCode"] for item in BUILTIN_ROLE_TEMPLATES}
    assert set(ROLE_PERMISSIONS) - {"PLATFORM_SUPER_ADMIN"} == template_codes


def test_teacher_row_accepts_multiple_codes_and_chinese_position_aliases():
    assert role_codes_from_row({"roleCodes": ["辅导员", "毕设导师", "INTERN_MENTOR"]}) == [
        "COUNSELOR", "GD_MENTOR", "INTERN_MENTOR",
    ]


def test_legacy_academic_alias_resolves_to_least_privilege_teacher_role():
    assert role_codes_from_row({"roleCode": "ACADEMIC"}) == ["ACADEMIC_TEACHER"]


def test_teacher_import_cannot_assign_school_admin():
    with pytest.raises(AppException) as exc:
        role_codes_from_row({"roleCode": "SCHOOL_ADMIN"})
    assert exc.value.code == "VALIDATION_ERROR"


def test_teacher_catalog_excludes_student_and_platform_roles():
    codes = {item["roleCode"] for item in role_catalog(teacher_only=True)["items"]}
    assert "STUDENT" not in codes
    assert "SCHOOL_ADMIN" not in codes
    assert "SYS_ADMIN" not in codes
    assert "SECURITY_AUDITOR" not in codes
    assert "PLATFORM_SUPER_ADMIN" not in codes


def test_identity_import_rejects_non_identity_entities(monkeypatch):
    monkeypatch.setattr(onboarding, "db_enabled", lambda: False)
    with pytest.raises(AppException) as exc:
        identity_import_service.run_identity_import(
            {"userType": "PLATFORM_SUPER_ADMIN"},
            {"tenantId": "1001", "colleges": [{"name": "信息学院"}]},
            dry_run=True,
        )
    assert exc.value.code == "VALIDATION_ERROR"
    assert "colleges" in exc.value.message


def test_identity_import_requires_at_least_one_account_row():
    with pytest.raises(AppException) as exc:
        identity_import_service.run_identity_import(
            {"userType": "PLATFORM_SUPER_ADMIN"}, {"tenantId": "1001"}, dry_run=True)
    assert exc.value.code == "VALIDATION_ERROR"


def test_identity_import_cannot_disable_atomic_transaction():
    with pytest.raises(AppException) as exc:
        identity_import_service.run_identity_import(
            {"userType": "PLATFORM_SUPER_ADMIN"},
            {"tenantId": "1001", "atomic": False,
             "students": [{"studentNo": "S001", "name": "学生"}]},
            dry_run=True,
        )
    assert exc.value.code == "VALIDATION_ERROR"
    assert "整批" in exc.value.message


def test_onboarding_dry_run_reports_accounts_roles_and_scopes_without_db(monkeypatch):
    monkeypatch.setattr(onboarding, "db_enabled", lambda: False)
    body = {
        "tenantId": "1001",
        "students": [{"studentNo": "S001", "name": "张同学"}],
        "teachers": [{
            "loginName": "T001", "name": "李老师",
            "roleCodes": ["辅导员", "毕设导师"],
            "scopeType": "CLASS", "scopeRef": "软件2401",
        }],
    }
    report = identity_import_service.run_identity_import(
        {"userType": "PLATFORM_SUPER_ADMIN"}, body, dry_run=True)
    assert report["errors"] == []
    assert report["entities"]["studentAccounts"]["created"] == 1
    assert report["entities"]["teachers"]["created"] == 1
    assert report["entities"]["roleBindings"]["created"] == 3
    assert report["entities"]["scopes"]["created"] == 1


def test_onboarding_rejects_unknown_role_instead_of_creating_it(monkeypatch):
    monkeypatch.setattr(onboarding, "db_enabled", lambda: False)
    report = identity_import_service.run_identity_import(
        {"userType": "PLATFORM_SUPER_ADMIN"},
        {"tenantId": "1001", "teachers": [{
            "loginName": "T001", "name": "李老师", "roleCode": "SUPER_TEACHER",
        }]},
        dry_run=True,
    )
    assert any(e["field"] == "roleCodes" for e in report["errors"])


def test_onboarding_public_channel_cannot_create_student_or_teacher_accounts():
    with pytest.raises(AppException) as exc:
        onboarding.run_onboarding(
            {"userType": "PLATFORM_SUPER_ADMIN"},
            {"tenantId": "1001", "students": [{"studentNo": "S001", "name": "学生"}]},
            dry_run=True,
        )
    assert exc.value.code == "VALIDATION_ERROR"
    assert "系统管理" in exc.value.message


def test_student_number_and_teacher_login_collision_is_rejected():
    errors = onboarding._validate_rows({
        "students": [{"studentNo": "10001", "name": "学生"}],
        "teachers": [{"loginName": "10001", "name": "老师", "roleCode": "ACADEMIC_TEACHER"}],
    })
    assert any("学号与教师登录名冲突" in e["error"] for e in errors)


def test_builtin_role_initialization_is_idempotent_without_committing():
    first_db = _FakeDb([[]])
    first = saas_role_service.ensure_builtin_roles(first_db, 1001)
    assert first["created"] == len(BUILTIN_ROLE_TEMPLATES)
    assert len(first_db.added) == len(BUILTIN_ROLE_TEMPLATES)
    existing = [SimpleNamespace(
        role_code=item["roleCode"], role_type="SYSTEM", is_deleted=False,
        status="ACTIVE", version=0, remark="") for item in BUILTIN_ROLE_TEMPLATES]
    second_db = _FakeDb([existing])
    second = saas_role_service.ensure_builtin_roles(second_db, 1001)
    assert second["unchanged"] == len(BUILTIN_ROLE_TEMPLATES)
    assert second_db.added == []


def test_disabled_builtin_role_is_restored_by_initialization():
    roles = [SimpleNamespace(
        role_code=item["roleCode"], role_type="SYSTEM", is_deleted=False,
        status="DISABLED" if item["roleCode"] == "STUDENT" else "ACTIVE",
        version=0, remark="", role_name="旧名称") for item in BUILTIN_ROLE_TEMPLATES]
    db = _FakeDb([roles])
    report = saas_role_service.ensure_builtin_roles(db, 1001)
    assert report["restored"] == 1
    student = next(role for role in roles if role.role_code == "STUDENT")
    assert student.status == "ACTIVE"
    assert student.role_name == "学生"


def test_only_system_administrators_have_identity_import_permission():
    assert has_permission({"currentRoleCode": "SCHOOL_ADMIN"}, "systemAdmin.user.import")
    assert has_permission({"currentRoleCode": "SYS_ADMIN"}, "systemAdmin.user.import")
    assert not has_permission({"currentRoleCode": "ACADEMIC_TEACHER"}, "systemAdmin.user.import")


def test_existing_user_gets_only_missing_role_binding():
    roles = [
        SimpleNamespace(id=1, role_code="COUNSELOR"),
        SimpleNamespace(id=2, role_code="GD_MENTOR"),
    ]
    existing_link = SimpleNamespace(
        role_id=1, is_deleted=False, status="ACTIVE", version=0)
    db = _FakeDb([roles, [existing_link]])
    report = saas_role_service.ensure_user_roles(
        db, 1001, 7, ["COUNSELOR", "GD_MENTOR"])
    assert report == {"created": 1, "restored": 0, "unchanged": 1}
    assert len(db.added) == 1


def test_graduation_and_internship_modules_never_create_login_accounts():
    app_dir = Path(__file__).resolve().parents[1] / "app" / "modules"
    offenders = []
    for domain in ("graduation", "internship"):
        for path in (app_dir / domain).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "User" for node in ast.walk(tree)):
                offenders.append(str(path))
    assert offenders == [], f"业务模块禁止隐式创建登录账号：{offenders}"


def test_frontend_exposes_batch_account_creation_only_at_fixed_system_route():
    root = Path(__file__).resolve().parents[2]
    dashboard = (root / "frontend/src/modules/system/views/SystemDashboardView.vue").read_text(
        encoding="utf-8")
    users = (root / "frontend/src/modules/system/views/SystemUserListView.vue").read_text(
        encoding="utf-8")
    routes = (root / "frontend/src/modules/system/system.routes.js").read_text(encoding="utf-8")
    assert "this.$router.push('/admin/system/identity-import')" in dashboard
    assert "this.$router.replace('/admin/system/identity-import')" in users
    assert "path: 'identity-import'" in routes
    assert "if (a.key === 'importUsers') return this.isIdentityImport" in users
