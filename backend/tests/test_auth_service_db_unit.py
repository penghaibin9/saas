"""真实认证/RBAC 主链纯单元测试。

本文件不创建引擎、不连接 MySQL、不执行 migration/seed；通过假 session 验证安全分支。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.services import auth_service_db as svc


class _FakeSession:
    def close(self):
        return None


class _TenantSession(_FakeSession):
    def __init__(self, status="ACTIVE", config_status="active"):
        self.tenant = SimpleNamespace(status=status)
        self.config = SimpleNamespace(config_json={"status": config_status})

    def get(self, model, key):
        return self.tenant

    def scalars(self, statement):
        return SimpleNamespace(first=lambda: self.config)


def _user(**overrides):
    base = {
        "id": 7,
        "tenant_id": 1001,
        "login_name": "teacher01",
        "real_name": "李老师",
        "user_type": "TEACHER",
        "version": 2,
        "must_change_password": False,
        "password_hash": "hash",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _ctx(role_id=10, code="COUNSELOR"):
    return svc._public_context(role_id, code, "辅导员")


def test_context_id_is_stable_and_scope_comes_from_role_policy():
    context = _ctx()
    assert context["contextId"] == "role:10"
    assert context["dataScope"] == "COUNSELOR_CLASSES"
    assert context["scopeLabel"] == "本人所带班级学生"


def test_unknown_role_defaults_to_assigned_not_school_wide():
    context = svc._public_context(99, "CUSTOM_TEST", "自定义测试角色")
    assert context["dataScope"] == "ASSIGNED"


def test_pick_context_never_returns_unowned_context():
    contexts = [_ctx(10, "COUNSELOR"), _ctx(11, "GD_MENTOR")]
    assert svc._pick_context(contexts, context_id="role:11")["roleCode"] == "GD_MENTOR"
    assert svc._pick_context(contexts, context_id="role:999") is None


def test_permission_version_changes_with_user_or_role_version():
    user = _user(version=3)
    c1 = _ctx()
    c1["version"] = 4
    c2 = _ctx(11, "GD_MENTOR")
    c2["version"] = 8
    assert svc._permission_version(user, [c1, c2]) == "u3|COUNSELOR:4,GD_MENTOR:8"


def test_tenant_gate_rejects_suspended_tenant():
    with pytest.raises(AppException) as exc:
        svc._ensure_tenant_login_allowed(_TenantSession("SUSPENDED"), _user())
    assert exc.value.code == "NO_PERMISSION"


def test_tenant_gate_rejects_expired_control_plane_status():
    with pytest.raises(AppException) as exc:
        svc._ensure_tenant_login_allowed(
            _TenantSession("ACTIVE", config_status="expired"), _user())
    assert exc.value.code == "NO_PERMISSION"


def test_platform_super_admin_is_not_bound_to_school_tenant_status():
    svc._ensure_tenant_login_allowed(
        _TenantSession("SUSPENDED"), _user(user_type="PLATFORM_SUPER_ADMIN"))


def test_login_without_active_role_is_fail_closed(monkeypatch):
    fake_db = _FakeSession()
    user = _user()
    monkeypatch.setattr(svc, "db_enabled", lambda: True)
    monkeypatch.setattr(svc, "get_sessionmaker", lambda: lambda: fake_db)
    monkeypatch.setattr(svc, "_find_login_user", lambda db, login, tenant: user)
    monkeypatch.setattr(svc, "verify_password", lambda plain, stored: True)
    monkeypatch.setattr(svc, "_role_contexts", lambda db, value: [])
    monkeypatch.setattr("app.services.audit_log.record", lambda *a, **k: None)

    with pytest.raises(AppException) as exc:
        svc.login_with_password("teacher01", "correct", "school-a")
    assert exc.value.code == "NO_PERMISSION"


def test_login_passes_tenant_code_to_account_resolution(monkeypatch):
    fake_db = _FakeSession()
    user = _user()
    seen = {}
    contexts = [_ctx()]
    monkeypatch.setattr(svc, "db_enabled", lambda: True)
    monkeypatch.setattr(svc, "get_sessionmaker", lambda: lambda: fake_db)
    monkeypatch.setattr(
        svc, "_find_login_user",
        lambda db, login, tenant: seen.update({"login": login, "tenant": tenant}) or user)
    monkeypatch.setattr(svc, "verify_password", lambda plain, stored: True)
    monkeypatch.setattr(svc, "_role_contexts", lambda db, value: contexts)
    monkeypatch.setattr(svc, "_ensure_tenant_login_allowed", lambda *a, **k: None)
    monkeypatch.setattr(svc, "_login_result", lambda *a, **k: {"ok": True})

    assert svc.login_with_password(" teacher01 ", "correct", " school-a ") == {"ok": True}
    assert seen == {"login": "teacher01", "tenant": "school-a"}


def test_switch_role_rejects_foreign_context_without_issuing_token(monkeypatch):
    fake_db = _FakeSession()
    user = _user()
    monkeypatch.setattr(svc, "get_sessionmaker", lambda: lambda: fake_db)
    monkeypatch.setattr(svc, "_load_token_user", lambda db, ctx: user)
    monkeypatch.setattr(svc, "_role_contexts", lambda db, value: [_ctx(10, "COUNSELOR")])
    monkeypatch.setattr(svc, "_login_result", lambda *a, **k: pytest.fail("不应签发令牌"))

    with pytest.raises(AppException) as exc:
        svc.switch_role({"userId": "db-7", "tenantId": "1001"}, "role:999", "PC")
    assert exc.value.code == "ROLE_NOT_FOUND"


def test_switch_role_revokes_old_context_and_returns_new_refresh(monkeypatch):
    fake_db = _FakeSession()
    user = _user()
    target = _ctx(11, "GD_MENTOR")
    calls = []
    monkeypatch.setattr(svc, "get_sessionmaker", lambda: lambda: fake_db)
    monkeypatch.setattr(svc, "_load_token_user", lambda db, ctx: user)
    monkeypatch.setattr(svc, "_role_contexts", lambda db, value: [_ctx(), target])
    monkeypatch.setattr(svc, "block_jti", lambda jti, exp: calls.append(("block", jti, exp)))
    monkeypatch.setattr(svc, "revoke_refresh_by_user", lambda uid: calls.append(("revoke", uid)))
    monkeypatch.setattr(
        svc, "_login_result",
        lambda *a, **k: {"accessToken": "new-access", "refreshToken": "new-refresh"})

    result = svc.switch_role({
        "userId": "db-7", "tenantId": "1001", "tokenJti": "old-jti", "tokenExp": 9999,
    }, "role:11", "MP")

    assert result["contextType"] == "GD_MENTOR"
    assert result["refreshToken"] == "new-refresh"
    assert calls == [("block", "old-jti", 9999), ("revoke", "db-7")]
