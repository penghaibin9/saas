"""历史 /authz 契约适配层纯单元测试；不创建引擎、不连接数据库。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import authz
from app.core.exceptions import AppException
from app.services import mock_rbac_service


def test_authz_login_delegates_to_real_auth_service_in_db_mode(monkeypatch):
    seen = {}
    monkeypatch.setattr(authz, "db_enabled", lambda: True)
    monkeypatch.setattr(
        authz.auth_service_db,
        "login_with_password",
        lambda login, password, tenant, client: seen.update({
            "login": login, "password": password, "tenant": tenant, "client": client,
        }) or {"userId": "db-7"},
    )
    monkeypatch.setattr(authz.audit_log, "record", lambda *a, **k: None)

    result = authz.login(authz.LoginBody(
        tenantCode=" school-a ", loginName=" teacher01 ", password="secret", clientType="PC"))

    assert result["data"]["userId"] == "db-7"
    assert seen == {
        "login": "teacher01", "password": "secret",
        "tenant": " school-a ", "client": "PC",
    }


def test_authz_login_cannot_use_mock_when_explicitly_disabled(monkeypatch):
    monkeypatch.setattr(authz, "db_enabled", lambda: False)
    monkeypatch.setattr(authz, "settings", SimpleNamespace(mock_login_enabled=False))
    with pytest.raises(AppException) as exc:
        authz.login(authz.LoginBody(loginName="admin01", password="anything"))
    assert exc.value.code == "NO_PERMISSION"


def test_real_school_admin_projects_admin_menu_not_teacher_menu():
    active = {"roleCode": "SCHOOL_ADMIN", "contextType": "SCHOOL_ADMIN"}
    assert mock_rbac_service._ui_kind({"userType": "SCHOOL_ADMIN"}, active) == "ADMIN"


def test_switching_admin_account_to_teacher_role_projects_teacher_menu():
    active = {"roleCode": "COUNSELOR", "contextType": "COUNSELOR"}
    assert mock_rbac_service._ui_kind({"userType": "SCHOOL_ADMIN"}, active) == "TEACHER"
