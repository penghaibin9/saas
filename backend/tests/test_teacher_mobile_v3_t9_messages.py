from types import SimpleNamespace
import inspect

import pytest

from app.core.exceptions import AppException
from app.services import teacher_mobile_messages_v3_service as svc


def _row(**kw):
    values = {"category": None, "message_type": None, "priority": None}
    values.update(kw)
    return SimpleNamespace(**values)


def test_t9_cursor_round_trip_and_signature_tamper(monkeypatch):
    monkeypatch.setattr(svc, "_cursor_signature", lambda raw: (raw[:1] or b"x") * 32)
    payload = {
        "v": 1,
        "filterHash": "filter-a",
        "eventAt": "2026-08-20T10:20:30.123456",
        "id": 123,
    }
    token = svc._encode_cursor(payload)
    decoded = svc._decode_cursor(token, expected_filter_hash="filter-a")
    assert decoded["id"] == 123
    assert decoded["eventAt"].isoformat(timespec="microseconds") == payload["eventAt"]

    body, signature = token.split(".", 1)
    tampered = f"{body}.{signature[:-1]}{'A' if signature[-1] != 'A' else 'B'}"
    with pytest.raises(AppException):
        svc._decode_cursor(tampered, expected_filter_hash="filter-a")

    with pytest.raises(AppException):
        svc._decode_cursor(token, expected_filter_hash="filter-b")


def test_t9_server_classification_has_single_priority_order():
    assert svc._classify_row(_row(priority="EMERGENCY", category="TODO")) == "risk"
    assert svc._classify_row(_row(message_type="REMINDER")) == "urge"
    assert svc._classify_row(_row(category="BUSINESS")) == "dynamic"
    assert svc._classify_row(_row(message_type="NOTICE")) == "system"


def test_t9_filter_contract_rejects_local_scan_inputs():
    assert svc._normalize_tab("system", allow_all=True) == "system"
    assert svc._normalize_tab("all", allow_all=True) == "all"
    assert svc._normalize_query("通知") == "通知"
    with pytest.raises(AppException):
        svc._normalize_tab("other", allow_all=True)
    with pytest.raises(AppException):
        svc._normalize_query("x")


def test_t9_keyset_source_has_no_offset_and_uses_page_size_plus_one():
    source = inspect.getsource(svc.list_messages)
    assert ".offset(" not in source
    assert ".limit(size + 1)" in source
    assert "UnifiedMessage.created_at < event_at" in source
    assert "UnifiedMessage.id < row_id" in source


def test_t9_staff_identity_does_not_bypass_canonical_message_permission(monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "enforce_permission", lambda user, code: calls.append((user["userId"], code)))
    user = {"userId": "db-7", "userType": "TEACHER"}

    assert svc._require_teacher(user) is user
    assert svc._require_teacher(user, permission="workbench.message.ack") is user
    assert calls == [
        ("db-7", "workbench.message.view"),
        ("db-7", "workbench.message.ack"),
    ]


def test_t9_student_identity_is_rejected_before_permission_check(monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "enforce_permission", lambda user, code: calls.append(code))
    with pytest.raises(AppException):
        svc._require_teacher({"userId": "db-8", "userType": "STUDENT"})
    assert calls == []
