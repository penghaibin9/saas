from __future__ import annotations

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException


def test_idempotency_replays_and_rejects_payload_reuse(monkeypatch):
    from app.core import idempotency

    records = {}
    monkeypatch.setattr(idempotency, "cache_get_json", lambda key: records.get(key))
    monkeypatch.setattr(idempotency, "cache_set_json",
                        lambda key, value, ttl: records.__setitem__(key, value) is None)
    user = {"tenantId": "101", "userId": "u-1"}
    set_tenant({"tenantId": "101"})
    try:
        cached, handle = idempotency.begin(user, "student-export", "request-0001", {"purpose": "核对名单"})
        assert cached is None and handle is not None
        idempotency.finish(handle, {"taskId": "55", "status": "SUCCESS"})

        cached, second_handle = idempotency.begin(
            user, "student-export", "request-0001", {"purpose": "核对名单"})
        assert cached == {"taskId": "55", "status": "SUCCESS"}
        assert second_handle is None

        with pytest.raises(AppException) as exc:
            idempotency.begin(user, "student-export", "request-0001", {"purpose": "其他用途"})
        assert exc.value.code == "DATA_CONFLICT"
    finally:
        set_tenant(None)


def test_idempotency_key_length_is_bounded():
    from app.core.idempotency import begin

    with pytest.raises(AppException) as exc:
        begin({"tenantId": "1", "userId": "u"}, "export", "short", {})
    assert exc.value.code == "VALIDATION_ERROR"
