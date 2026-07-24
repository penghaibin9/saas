"""P1-NEW：调度频率、时区解析、幂等 abort、消息同事务修复入口。"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.core.exceptions import AppException
from app.core.idempotency import abort, begin, fail, finish, idempotency_guard
from app.core.timeutil import iso_utc, parse_api_datetime, to_utc_naive


def test_parse_api_datetime_rfc3339_with_offset():
    dt = parse_api_datetime("2026-07-24T10:00:00+08:00")
    assert dt is not None
    # 10:00+08 = 02:00 UTC
    assert dt.hour == 2
    assert dt.tzinfo is None


def test_parse_api_datetime_zulu():
    dt = parse_api_datetime("2026-07-24T02:00:00Z")
    assert dt is not None
    assert dt.hour == 2


def test_iso_utc_appends_z():
    naive = datetime(2026, 7, 24, 2, 0, 0)
    assert iso_utc(naive).endswith("Z")


def test_naive_local_interpreted_as_tenant_tz():
    # Asia/Shanghai: 10:00 local → 02:00 UTC
    dt = to_utc_naive(datetime(2026, 7, 24, 10, 0, 0))
    assert dt.hour == 2


def test_idempotency_abort_releases(monkeypatch):
    store = {}

    def _get(k):
        return store.get(k)

    def _set_absent(k, v, ttl):
        if k in store:
            return False
        store[k] = v
        return True

    def _set(k, v, ttl):
        store[k] = v

    def _del(*keys):
        for k in keys:
            store.pop(k, None)
        return 1

    monkeypatch.setattr("app.core.idempotency.cache_get_json", _get)
    monkeypatch.setattr("app.core.idempotency.cache_set_json_if_absent", _set_absent)
    monkeypatch.setattr("app.core.idempotency.cache_set_json", _set)
    monkeypatch.setattr("app.core.idempotency.cache_delete", _del)

    user = {"userId": "u1", "tenantId": "1"}
    cached, handle = begin(user, "op", "idem-key-12345678", {"a": 1})
    assert cached is None and handle
    abort(handle)
    cached2, handle2 = begin(user, "op", "idem-key-12345678", {"a": 1})
    assert cached2 is None and handle2


def test_idempotency_guard_releases_on_exception(monkeypatch):
    store = {}

    monkeypatch.setattr("app.core.idempotency.cache_get_json", lambda k: store.get(k))
    monkeypatch.setattr(
        "app.core.idempotency.cache_set_json_if_absent",
        lambda k, v, ttl: store.setdefault(k, v) is v or False if k in store and store[k] is not v else (store.__setitem__(k, v) or True),
    )
    monkeypatch.setattr("app.core.idempotency.cache_set_json", lambda k, v, ttl: store.__setitem__(k, v))
    monkeypatch.setattr("app.core.idempotency.cache_delete", lambda *keys: [store.pop(k, None) for k in keys])

    # simplify set_absent
    def set_absent(k, v, ttl):
        if k in store:
            return False
        store[k] = v
        return True

    monkeypatch.setattr("app.core.idempotency.cache_set_json_if_absent", set_absent)

    user = {"userId": "u1", "tenantId": "1"}
    with pytest.raises(RuntimeError):
        with idempotency_guard(user, "op2", "idem-key-abcdefgh", {"x": 1}) as g:
            assert g.cached is None
            raise RuntimeError("boom")
    # 释放后可再次 begin
    cached, handle = begin(user, "op2", "idem-key-abcdefgh", {"x": 1})
    assert handle is not None


def test_scheduler_includes_trial_tenants():
    from scripts import run_scheduled_jobs as sched
    src = open(sched.__file__, encoding="utf-8").read()
    assert "TRIAL" in src
    assert "INTERVAL_DELIVERY" in src
    assert "job_delivery_and_outbox" in src


def test_fingerprint_mismatch():
    from app.core.idempotency import begin
    store = {}

    def set_absent(k, v, ttl):
        if k in store:
            return False
        store[k] = v
        return True

    import app.core.idempotency as mod
    mod.cache_get_json = lambda k: store.get(k)
    mod.cache_set_json_if_absent = set_absent
    mod.cache_set_json = lambda k, v, ttl: store.__setitem__(k, v)
    mod.cache_delete = lambda *keys: [store.pop(k, None) for k in keys]

    user = {"userId": "u1", "tenantId": "1"}
    _, h = begin(user, "op3", "idem-key-mismatch1", {"a": 1})
    finish(h, {"ok": True})
    with pytest.raises(AppException) as ei:
        begin(user, "op3", "idem-key-mismatch1", {"a": 2})
    assert ei.value.code == "DATA_CONFLICT"
