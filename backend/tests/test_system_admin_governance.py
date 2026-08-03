"""系统管理商业化治理：模块门禁 / 有效权限 / 同步假成功 / 数据范围 / 组织校验。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_module_manifest_validates():
    import subprocess
    script = ROOT / "scripts" / "check" / "validate-module-manifest.py"
    r = subprocess.run(["python", str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_employment_feature_key_independent():
    from app.core.module_registry import resolve_feature_key
    assert resolve_feature_key("employment") == "employment"
    assert resolve_feature_key("internship") == "internship"
    assert resolve_feature_key("graduationDesign") == "graduation"
    assert resolve_feature_key("academicLegacy") == "academicAffairs"
    assert resolve_feature_key("unknown_xyz_module") is None


def test_feature_enabled_unknown_denied(monkeypatch):
    from app.services import platform_service as ps
    monkeypatch.setattr(ps, "effective_features", lambda tid: {"internship": True})
    assert ps.feature_enabled(1, "internship") is True
    assert ps.feature_enabled(1, "not_a_real_feature_key") is False


def test_route_registration_gates():
    text = (ROOT / "backend" / "app" / "api" / "v1" / "route_registration.py").read_text(encoding="utf-8")
    assert 'require_module("employment")' in text or 'deps["employment"]' in text
    assert 'deps["orientation"]' in text
    assert 'deps["academic_legacy"]' in text
    assert 'employment.router, dependencies=deps["intern"]' not in text


def test_sync_job_cannot_fake_success(monkeypatch):
    from app.services import system_governance_service as gov

    stored = {}

    def fake_load(key):
        return stored.get(key, [] if key != gov.DOC_MODULE_FEATURES else {})

    def fake_save(key, payload, user=None):
        stored[key] = payload
        return 1

    monkeypatch.setattr(gov, "_load", fake_load)
    monkeypatch.setattr(gov, "_save", fake_save)
    monkeypatch.setattr(gov, "_tid", lambda: 1)

    row = gov.enqueue_sync_job({"realName": "t"}, {"name": "x", "integrationId": "1"})
    assert row["status"] == "PENDING"
    assert row["status"] != "SUCCESS"

    with pytest.raises(Exception):
        gov.run_sync_job_executor(row["id"], {"realName": "t"})


def test_custom_scope_requires_targets():
    from app.core.exceptions import AppException
    from app.services.data_scope_service import save_role_scope

    class _Role:
        tenant_id = 1
        role_code = "CUSTOM_X"
        remark = ""

    with pytest.raises(AppException):
        save_role_scope(_Role(), "CUSTOM", target_json={})


def test_effective_permission_patterns_builtin():
    from app.core.permissions import get_effective_permission_patterns, has_permission
    user = {"currentRoleCode": "SCHOOL_ADMIN", "tenantId": "1"}
    patterns = get_effective_permission_patterns(user)
    assert "*" in patterns or any(p.endswith(".*") for p in patterns) or len(patterns) > 0
    assert has_permission(user, "systemAdmin.dashboard.view") is True


def test_audit_module_not_hardcoded_system():
    text = (ROOT / "backend" / "app" / "api" / "v1" / "system.py").read_text(encoding="utf-8")
    assert '"module": "SYSTEM", "moduleLabel": "系统管理"' not in text
    assert "_audit_module_of" in text


def test_phone_update_uses_encrypt():
    text = (ROOT / "backend" / "app" / "api" / "v1" / "system.py").read_text(encoding="utf-8")
    assert "encrypt_field(phone)" in text
    assert "account.phone_encrypted = phone\n" not in text


def test_module_phone_writes_use_encrypt_field():
    """敏感字段写入收口：关键模块不得再明文赋给 *_encrypted。"""
    samples = [
        ROOT / "backend/app/services/orientation_service.py",
        ROOT / "backend/app/modules/employment/services/employment_service.py",
        ROOT / "backend/app/services/academic_service.py",
        ROOT / "backend/app/modules/internship/services/internship_enterprise_service.py",
        ROOT / "backend/app/modules/graduation/services/graduation_mentor_service.py",
        ROOT / "backend/app/student_portal/services/parent_link_service.py",
    ]
    for path in samples:
        text = path.read_text(encoding="utf-8")
        assert "encrypt_field" in text, path.name
        # 禁止典型明文直写（允许 decrypt/encrypt 调用行）
        assert "phone_encrypted=body.get(\"phone\")" not in text
        assert "phone_encrypted=body.get('phone')" not in text
        assert "guardian_phone_encrypted=phone," not in text


def test_auth_scope_prefers_structured_rule():
    """登录上下文与 system._role_scope 对齐：优先 resolve_role_scope_code。"""
    import inspect
    from app.services import auth_service_db as auth
    src = inspect.getsource(auth._scope_from_role)
    assert "resolve_role_scope_code" in src


def test_data_scope_survives_context_rebuild(monkeypatch):
    """改范围后，认证重建上下文仍优先读结构化规则（不依赖外部数据库可用性）。"""
    from app.services import auth_service_db as auth
    from app.services import data_scope_service as dss

    class Role:
        id = 9
        tenant_id = 1000000000000000001
        role_code = "SCHOOL_ADMIN"
        role_name = "学校管理员"
        version = 0
        remark = ";scope=TENANT;permMode=DB"

    # 模拟已写入 DataScopeRule=COLLEGE 后的读取
    monkeypatch.setattr(dss, "resolve_role_scope_code", lambda role: "COLLEGE")

    assert auth._scope_from_role(Role()) == "COLLEGE"
    rebuilt = auth._public_context(
        Role.id,
        Role.role_code,
        Role.role_name,
        scope=auth._scope_from_role(Role()),
        version=Role.version,
    )
    scope = rebuilt.get("dataScope")
    assert scope == "COLLEGE", f"context scope={scope!r}"


def test_module_storage_failure_never_defaults_enabled(monkeypatch):
    from app.core.exceptions import AppException
    from app.services import module_access_service as access
    from app.services import system_governance_service as gov

    # get_module_features 自 SYS-13 起接受可选 tenant_id（模块门禁按租户读取）
    monkeypatch.setattr(gov, "get_module_features", lambda *_a, **_k: (_ for _ in ()).throw(
        AppException("SERVER_ERROR", "storage down", http_status=503)))
    with pytest.raises(AppException) as caught:
        access._school_enabled_map(1)
    assert caught.value.http_status == 503


def test_module_feature_expected_version_conflict(monkeypatch):
    from app.core.exceptions import AppException
    from app.db import session as db_session
    from app.services import system_governance_service as gov

    monkeypatch.setattr(db_session, "db_enabled", lambda: False)
    monkeypatch.setattr(gov, "_tid", lambda: 0)
    gov._MEMORY_DOCS.pop(gov.DOC_MODULE_FEATURES, None)
    gov._MEMORY_DOCS.pop(f"{gov.DOC_MODULE_FEATURES}__ver", None)
    first = gov.save_module_features(
        {"userId": "db-1"},
        {"studentAffairs": {"enabled": False}},
        "收口并发版本测试",
        expected_version=0,
    )
    assert first["studentAffairs"]["version"] == 1
    with pytest.raises(AppException) as caught:
        gov.save_module_features(
            {"userId": "db-1"},
            {"studentAffairs": {"enabled": True}},
            "使用过期版本重试",
            expected_version=0,
        )
    assert caught.value.code == "DATA_CONFLICT"
    gov._MEMORY_DOCS.pop(gov.DOC_MODULE_FEATURES, None)
    gov._MEMORY_DOCS.pop(f"{gov.DOC_MODULE_FEATURES}__ver", None)


def test_delegation_rejects_platform_and_excess_role():
    from datetime import datetime, timedelta
    from app.core.exceptions import AppException
    from app.services import system_governance_service as gov

    base = {
        "granteeUserNo": "teacher01",
        "expiresAt": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "reason": "系统收口越权验证",
    }
    with pytest.raises(AppException) as platform_denied:
        gov.create_delegation(
            {"currentRoleCode": "SCHOOL_ADMIN"},
            {**base, "roleCode": "PLATFORM_SUPER_ADMIN"},
        )
    assert platform_denied.value.code == "NO_PERMISSION"

    with pytest.raises(AppException) as excess_denied:
        gov.create_delegation(
            {"currentRoleCode": "SYS_ADMIN"},
            {**base, "roleCode": "COUNSELOR"},
        )
    assert excess_denied.value.code == "NO_PERMISSION"


def test_delegation_matches_stable_user_id_after_login_rename(monkeypatch):
    from datetime import datetime, timedelta
    from app.db import session as db_session
    from app.services import system_governance_service as gov

    monkeypatch.setattr(db_session, "db_enabled", lambda: False)
    monkeypatch.setattr(gov, "_tid", lambda: 0)
    gov._MEMORY_DOCS[gov.DOC_DELEGATIONS] = [{
        "id": "delegation-1",
        "granteeUserId": "42",
        "granteeUserNo": "old-login",
        "roleCode": "COUNSELOR",
        "expiresAt": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ACTIVE",
        "effective": True,
    }]
    patterns = gov.active_delegation_permission_patterns({
        "userId": "db-42",
        "loginName": "new-login",
    })
    assert patterns
    gov._MEMORY_DOCS.pop(gov.DOC_DELEGATIONS, None)


def test_org_bypass_allowlist_documented():
    from app.services.org_master_service import ORG_WRITE_BYPASS_ALLOWLIST
    assert "sandbox_service" in ORG_WRITE_BYPASS_ALLOWLIST
    assert "academic_affairs_major_split_service" in ORG_WRITE_BYPASS_ALLOWLIST


def test_system_catalog_nine_workspaces():
    # 通过读取前端目录源文件统计二级工作区
    text = (ROOT / "frontend" / "src" / "modules" / "system" / "systemManagementCatalog.js").read_text(encoding="utf-8")
    assert "系统总览" in text
    assert "实施与验收" in text
    assert "身份与账号" in text
    assert "组织与任职" in text
    assert "角色权限与数据范围" in text
    assert "模块与学校配置" in text
    assert "流程配置与运行" in text
    assert "安全与审计" in text
    assert "接口同步与数据迁移" in text
