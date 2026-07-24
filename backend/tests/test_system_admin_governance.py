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
