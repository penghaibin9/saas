from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.exceptions import AppException


def _request(method: str) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": "/api/v1/internship/enterprise-portal/company",
        "raw_path": b"/api/v1/internship/enterprise-portal/company",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
    })


class _Db:
    def __init__(self, company):
        self.company = company
        self.closed = False

    def scalar(self, _query):
        return self.company

    def close(self):
        self.closed = True


def _install_principal_dependencies(monkeypatch, *, tenant_id: int = 88001):
    from app.modules.internship.dependencies import enterprise_context as enterprise
    from app.services import module_access_service

    claims = {"tenantId": str(tenant_id), "tenantName": "商业门禁测试校", "jti": "enterprise-test"}
    tenant = SimpleNamespace(id=tenant_id, tenant_code=f"ent-{tenant_id}")
    user = SimpleNamespace(id=9001)
    member = SimpleNamespace(id=9101, company_id=9201, member_role="HR")
    company = SimpleNamespace(
        status="ACTIVE", blacklist=False, coop_status="ACTIVE",
        qualification_status="PASSED", access_valid_until=None,
    )
    db = _Db(company)
    monkeypatch.setattr(
        enterprise.auth_svc,
        "decode_and_validate_access",
        lambda _token: (claims, tenant, user, member),
    )
    monkeypatch.setattr(enterprise, "get_sessionmaker", lambda: (lambda: db))
    monkeypatch.setattr(enterprise, "auth_session_blocked", lambda _sid: False)
    calls = []
    monkeypatch.setattr(
        module_access_service,
        "assert_module_access",
        lambda tid, key, *, write=False: calls.append((tid, key, write)) or {"allowed": True},
    )
    return enterprise, module_access_service, db, calls


def test_enterprise_get_uses_same_tenant_commercial_module_gate(monkeypatch):
    enterprise, _, db, calls = _install_principal_dependencies(monkeypatch)
    principal = enterprise.get_enterprise_principal(
        request=_request("GET"), authorization="Bearer enterprise-token",
    )
    assert principal.tenant_id == 88001
    assert principal.member_role == "HR"
    assert calls == [(88001, "internship", False)]
    assert db.closed is True


def test_enterprise_unsafe_request_installs_write_capable_module_gate(monkeypatch):
    enterprise, _, _, calls = _install_principal_dependencies(monkeypatch, tenant_id=88002)
    enterprise.get_enterprise_principal(
        request=_request("POST"), authorization="Bearer enterprise-token",
    )
    assert calls == [(88002, "internship", True)]


def test_enterprise_role_and_grant_cannot_bypass_unpurchased_or_frozen_module(monkeypatch):
    enterprise, module_access, _, calls = _install_principal_dependencies(monkeypatch, tenant_id=88003)

    def deny(tid, key, *, write=False):
        calls.append((tid, key, write))
        raise AppException(
            "NO_PERMISSION", "模块未购买或已冻结",
            details={"moduleKey": key}, http_status=403,
        )

    monkeypatch.setattr(module_access, "assert_module_access", deny)
    with pytest.raises(AppException) as caught:
        enterprise.get_enterprise_principal(
            request=_request("PUT"), authorization="Bearer enterprise-token",
        )
    assert caught.value.http_status == 403
    assert calls[-1] == (88003, "internship", True)


def test_enterprise_module_outage_propagates_503_instead_of_falling_back_to_grant(monkeypatch):
    enterprise, module_access, _, _ = _install_principal_dependencies(monkeypatch, tenant_id=88004)

    def unavailable(*_args, **_kwargs):
        raise AppException(
            "AUTHORITY_UNAVAILABLE", "商业授权服务暂不可用",
            details={"retryable": True}, http_status=503,
        )

    monkeypatch.setattr(module_access, "assert_module_access", unavailable)
    with pytest.raises(AppException) as caught:
        enterprise.get_enterprise_principal(
            request=_request("GET"), authorization="Bearer enterprise-token",
        )
    assert caught.value.code == "AUTHORITY_UNAVAILABLE"
    assert caught.value.http_status == 503
