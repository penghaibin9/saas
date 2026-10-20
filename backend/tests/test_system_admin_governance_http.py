"""系统管理治理 ASGI/HTTP 关键路径（不绕过 Depends）。"""
from __future__ import annotations


def test_go_live_checks_http(client, auth_headers):
    resp = client.get("/api/v1/system/go-live-checks", headers=auth_headers)
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        body = resp.json()
        data = body.get("data") or body
        assert "summary" in data
        assert set(data["summary"]).issuperset({"blocker", "advisory", "passed", "na"})
        assert "items" in data
        assert data.get("canGoLive") is not None
        # 禁止一条总分掩盖问题
        assert isinstance(data["items"], list)


def test_overview_board_http(db_mode, client, auth_headers):
    # The overview reads the commercial ledger. Use the isolated paid-order/IAM
    # baseline instead of accepting an authority outage as a successful response.
    resp = client.get("/api/v1/system/overview-board", headers=auth_headers)
    assert resp.status_code == 200, resp.json()
    assert resp.json()["code"] == 0
    assert isinstance(resp.json()["data"], dict)


def test_system_context_uses_effective_permissions(client, auth_headers):
    resp = client.get("/api/v1/system/context", headers=auth_headers)
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        data = resp.json().get("data") or {}
        assert "permissionPatterns" in data
        assert "permissionVersion" in data or data.get("permissionPatterns") is not None


def test_rbac_current_context_effective(client, auth_headers):
    resp = client.get("/api/v1/rbac/current-context", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json().get("data") or {}
    assert isinstance(data.get("permissionPatterns"), list)
    assert len(data["permissionPatterns"]) > 0


def test_sync_enqueue_not_success_http(client, auth_headers):
    resp = client.post(
        "/api/v1/system/sync-jobs",
        headers=auth_headers,
        json={"name": "governance-test-sync", "integrationId": ""},
    )
    if resp.status_code in (401, 403):
        return
    assert resp.status_code == 200
    data = (resp.json().get("data") or resp.json())
    assert data.get("status") != "SUCCESS"
    assert data.get("status") in ("PENDING", "FAILED")


def test_overview_board_authority_outage_remains_503(client, auth_headers, monkeypatch):
    from app.services import commercial_entitlement_authority_service as commercial

    # Only the read IO envelope is faulted. The real HTTP route, Depends and
    # strict authority adapter must still reject; never broaden the positive test.
    monkeypatch.setattr(commercial, "commercial_state", lambda _tid: {
        "verified": False, "authoritySource": "MODULE_V2_UNAVAILABLE",
        "features": {"internship": False},
    })
    resp = client.get("/api/v1/system/overview-board", headers=auth_headers)
    assert resp.status_code == 503, resp.json()
    assert resp.json()["bizCode"] == "AUTHORITY_UNAVAILABLE"
    assert resp.json()["data"] is None
