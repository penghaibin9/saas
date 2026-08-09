from collections import defaultdict


def test_module_access_reuses_heavy_snapshots_within_same_http_trace(monkeypatch):
    from app.core import context as request_context
    from app.services import module_access_service as svc
    from app.services import platform_service
    from app.services import system_governance_service as gov
    from app.services import tenant_effective_state_service as tenant_state

    calls = defaultdict(int)
    trace = {"value": "req-rbac-snapshot-1"}

    monkeypatch.setattr(request_context, "get_trace_id", lambda: trace["value"])

    def fake_features(_tenant_id):
        calls["features"] += 1
        return defaultdict(lambda: True)

    def fake_school_gate(_tenant_id):
        calls["school"] += 1
        return {}

    def fake_effective_state(_tenant_id, strict=False):
        calls["tenant"] += 1
        return {"effectiveStatus": "ACTIVE", "errors": []}

    monkeypatch.setattr(platform_service, "effective_features", fake_features)
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
    from app.services import platform_service
    from app.services import system_governance_service as gov
    from app.services import tenant_effective_state_service as tenant_state

    calls = defaultdict(int)
    monkeypatch.setattr(request_context, "get_trace_id", lambda: "-")

    monkeypatch.setattr(platform_service, "effective_features", lambda _tid: calls.__setitem__("features", calls["features"] + 1) or defaultdict(lambda: True))
    monkeypatch.setattr(gov, "get_module_features", lambda _tid: calls.__setitem__("school", calls["school"] + 1) or {})
    monkeypatch.setattr(tenant_state, "get_effective_state", lambda _tid, strict=False: calls.__setitem__("tenant", calls["tenant"] + 1) or {"effectiveStatus": "ACTIVE", "errors": []})
    svc._request_snapshot.set(None)

    svc.module_access_state(1000000000000000007, "internship")
    svc.module_access_state(1000000000000000007, "graduation")

    assert calls == {"features": 2, "school": 2, "tenant": 2}
    svc._request_snapshot.set(None)
