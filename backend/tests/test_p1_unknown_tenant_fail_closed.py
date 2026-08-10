"""P0：显式指定不存在的租户必须被拒绝，不得静默回落默认租户。

历史行为：core/tenant_context.resolve_tenant() 在 _MOCK_TENANTS 里查不到
X-Tenant 指定的 code 时，直接 `or _MOCK_TENANTS.get(DEFAULT_TENANT_CODE)`，
于是"随手写一个不存在的学校编码"的请求会落到默认学校的数据上。
"""
from __future__ import annotations


def test_unknown_tenant_header_is_rejected(client):
    resp = client.get("/api/v1/authz/me", headers={"X-Tenant": "no-such-school-zzz"})
    assert resp.status_code == 400
    assert resp.json()["bizCode"] == "TENANT_NOT_FOUND"


def test_unknown_tenant_query_param_is_rejected(client):
    resp = client.get("/api/v1/authz/me?tenant=no-such-school")
    assert resp.status_code == 400
    assert resp.json()["bizCode"] == "TENANT_NOT_FOUND"


def test_missing_tenant_still_falls_back_to_default(client):
    """没传租户 ≠ 传了个错的：不传仍走默认租户，不能把正常请求也打死。"""
    resp = client.get("/api/v1/authz/me")
    assert resp.status_code != 400 or resp.json().get("bizCode") != "TENANT_NOT_FOUND"


def test_known_tenant_header_still_works(client):
    resp = client.get("/api/v1/authz/me", headers={"X-Tenant": "demo"})
    assert not (resp.status_code == 400
                and resp.json().get("bizCode") == "TENANT_NOT_FOUND")
