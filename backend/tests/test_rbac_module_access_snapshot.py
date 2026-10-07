from collections import defaultdict

import pytest


@pytest.fixture(autouse=True)
def _isolate_module_snapshot(monkeypatch):
    """These are read-IO unit contracts, not database integration tests."""
    from app.core.config import settings
    from app.services import module_access_service as svc

    monkeypatch.setattr(settings, "DB_ENABLED", False)
    token = svc._request_snapshot.set(None)
    try:
        yield
    finally:
        svc._request_snapshot.reset(token)


def _verified_authority(features):
    return {"verified": True, "authoritySource": "MODULE_V2", "features": features}


def test_capability_projection_reads_commercial_authority_once_and_never_reuses_it(monkeypatch):
    from app.services import platform_service
    from app.services import tenant_capability_setting_service as caps

    calls = []
    enabled = {"internship": True, "graduation": True}
    monkeypatch.setattr(caps, "_load_rows", lambda _tid: {})
    monkeypatch.setattr(caps, "_legacy_enabled", lambda _tid: {})

    def features(tid):
        calls.append(tid)
        return dict(enabled)

    monkeypatch.setattr(platform_service, "effective_features", features)
    first = caps.capability_states(9001)
    assert first["internship"]["entitled"] is True
    assert calls == [9001]

    enabled["internship"] = False
    assert caps.capability_states(9001)["internship"]["entitled"] is False
    assert caps.capability_states(9002)["internship"]["entitled"] is False
    assert calls == [9001, 9001, 9002]

    # A missing commercial decision must not grant a module through defaults.
    enabled.pop("internship")
    assert caps.capability_states(9001)["internship"]["entitled"] is False

    def unavailable(_tid):
        raise RuntimeError("commercial authority unavailable")

    monkeypatch.setattr(platform_service, "effective_features", unavailable)
    failed = caps.capability_states(9001)
    assert all(not row["entitled"] for row in failed.values() if row["entitlementRequired"])


def _entitled_features() -> dict[str, bool]:
    """Use real manifest feature keys; dict.get() does not trigger defaultdict factories."""
    return {"internship": True, "graduation": True}


def test_module_access_reuses_heavy_snapshots_within_same_http_trace(monkeypatch):
    from app.core import context as request_context
    from app.services import module_access_service as svc
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import system_governance_service as gov
    from app.services import tenant_effective_state_service as tenant_state

    calls = defaultdict(int)
    trace = {"value": "req-rbac-snapshot-1"}

    monkeypatch.setattr(request_context, "get_trace_id", lambda: trace["value"])

    def fake_features(_tenant_id):
        calls["features"] += 1
        return _verified_authority(_entitled_features())

    def fake_school_gate(_tenant_id):
        calls["school"] += 1
        return {}

    def fake_effective_state(_tenant_id, strict=False):
        calls["tenant"] += 1
        return {"effectiveStatus": "ACTIVE", "errors": []}

    # Exercise strict envelope validation and cache semantics on the real read path.
    monkeypatch.setattr(commercial, "commercial_state", fake_features)
    monkeypatch.setattr(gov, "get_module_features", fake_school_gate)
    monkeypatch.setattr(tenant_state, "get_effective_state", fake_effective_state)
    svc._request_snapshot.set(None)

    internship = svc.module_access_state(1000000000000000007, "internship")
    graduation = svc.module_access_state(1000000000000000007, "graduation")

    assert internship["allowed"] is True
    assert graduation["allowed"] is True
    assert calls == {"features": 1, "school": 1, "tenant": 1}

    # 新 HTTP trace 必须重新读取，绝不能跨请求复用旧授权状态。
    trace["value"] = "req-rbac-snapshot-2"
    svc.module_access_state(1000000000000000007, "internship")
    assert calls == {"features": 2, "school": 2, "tenant": 2}
    svc._request_snapshot.set(None)


def test_module_access_without_http_trace_never_reuses_snapshot(monkeypatch):
    from app.core import context as request_context
    from app.services import module_access_service as svc
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import system_governance_service as gov
    from app.services import tenant_effective_state_service as tenant_state

    calls = defaultdict(int)
    monkeypatch.setattr(request_context, "get_trace_id", lambda: "-")

    def fake_features(_tenant_id):
        calls["features"] += 1
        return _verified_authority(_entitled_features())

    # Exercise strict envelope validation and cache semantics on the real read path.
    monkeypatch.setattr(commercial, "commercial_state", fake_features)
    monkeypatch.setattr(gov, "get_module_features", lambda _tid: calls.__setitem__("school", calls["school"] + 1) or {})
    monkeypatch.setattr(tenant_state, "get_effective_state", lambda _tid, strict=False: calls.__setitem__("tenant", calls["tenant"] + 1) or {"effectiveStatus": "ACTIVE", "errors": []})
    svc._request_snapshot.set(None)

    internship = svc.module_access_state(1000000000000000007, "internship")
    graduation = svc.module_access_state(1000000000000000007, "graduation")

    assert internship["allowed"] is True
    assert graduation["allowed"] is True
    assert calls == {"features": 2, "school": 2, "tenant": 2}
    svc._request_snapshot.set(None)


def test_same_trace_different_tenant_cannot_reuse_entitlement(monkeypatch):
    from app.core import context as request_context
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import module_access_service as svc
    from app.services import system_governance_service as gov
    from app.services import tenant_effective_state_service as tenant_state

    calls = []
    monkeypatch.setattr(request_context, "get_trace_id", lambda: "tenant-isolation")
    monkeypatch.setattr(gov, "get_module_features", lambda _tid: {})
    monkeypatch.setattr(tenant_state, "get_effective_state",
                        lambda _tid, strict=False: {"effectiveStatus": "ACTIVE", "errors": []})

    def authority(tid):
        calls.append(tid)
        return _verified_authority({"internship": tid == 9001})

    monkeypatch.setattr(commercial, "commercial_state", authority)
    assert svc.module_access_state(9001, "internship")["allowed"] is True
    denied = svc.module_access_state(9002, "internship")
    assert denied["allowed"] is False and denied["reasonCode"] == "NOT_ENTITLED"
    assert calls == [9001, 9002]


def test_next_request_observes_revocation_without_stale_cache(monkeypatch):
    from app.core import context as request_context
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import module_access_service as svc
    from app.services import system_governance_service as gov
    from app.services import tenant_effective_state_service as tenant_state

    trace = {"value": "before-revocation"}
    allowed = {"value": True}
    calls = []
    monkeypatch.setattr(request_context, "get_trace_id", lambda: trace["value"])
    monkeypatch.setattr(gov, "get_module_features", lambda _tid: {})
    monkeypatch.setattr(tenant_state, "get_effective_state",
                        lambda _tid, strict=False: {"effectiveStatus": "ACTIVE", "errors": []})

    def authority(tid):
        calls.append(tid)
        return _verified_authority({"internship": allowed["value"]})

    monkeypatch.setattr(commercial, "commercial_state", authority)
    assert svc.module_access_state(9001, "internship")["allowed"] is True
    allowed["value"] = False
    trace["value"] = "after-revocation"
    assert svc.module_access_state(9001, "internship")["allowed"] is False
    assert calls == [9001, 9001]


def test_faulted_authority_is_not_cached_and_same_request_recovers(monkeypatch):
    from app.core import context as request_context
    from app.core.exceptions import AppException
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import module_access_service as svc
    from app.services import system_governance_service as gov
    from app.services import tenant_effective_state_service as tenant_state

    calls = []
    states = iter([
        {"verified": False, "authoritySource": "MODULE_V2_UNAVAILABLE", "features": {"internship": False}},
        _verified_authority({"internship": True}),
    ])
    monkeypatch.setattr(request_context, "get_trace_id", lambda: "recover-in-request")
    monkeypatch.setattr(gov, "get_module_features", lambda _tid: {})
    monkeypatch.setattr(tenant_state, "get_effective_state",
                        lambda _tid, strict=False: {"effectiveStatus": "ACTIVE", "errors": []})

    def authority(tid):
        calls.append(tid)
        return next(states)

    monkeypatch.setattr(commercial, "commercial_state", authority)
    with pytest.raises(AppException) as caught:
        svc.module_access_state(9001, "internship")
    assert caught.value.http_status == 503 and caught.value.code == "AUTHORITY_UNAVAILABLE"
    assert svc._request_snapshot.get() is None
    assert svc.module_access_state(9001, "internship")["allowed"] is True
    assert calls == [9001, 9001]
