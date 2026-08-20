from __future__ import annotations

import inspect

import pytest

from app.api.v1 import todos as todos_api
from app.core.exceptions import AppException
from app.services import teacher_mobile_todo_keyset_service as keyset_svc
from app.services import teacher_mobile_todo_read_service as read_svc


def _sample_cursor_payload(**overrides):
    payload = {
        "v": 1,
        "filterHash": "abc123",
        "asOf": "2026-08-20T00:00:00.000000",
        "dueBucket": 0,
        "dueAt": "2026-08-21T08:30:00.000000",
        "id": 99,
        "total": 41,
        "statusCounts": {"PENDING": 30, "DONE": 11},
    }
    payload.update(overrides)
    return payload


def test_t2_cursor_roundtrip_carries_frozen_seek_contract():
    payload = _sample_cursor_payload()
    cursor = keyset_svc._encode_cursor(payload)
    decoded = keyset_svc._decode_cursor(cursor, expected_filter_hash="abc123")

    assert decoded["filterHash"] == "abc123"
    assert decoded["asOf"] == payload["asOf"]
    assert decoded["dueBucket"] == 0
    assert decoded["dueAt"] == payload["dueAt"]
    assert decoded["id"] == 99
    assert decoded["total"] == 41
    assert decoded["statusCounts"] == {"PENDING": 30, "DONE": 11}
    assert cursor.count(".") == 1


def test_t2_cursor_rejects_filter_reuse_across_query_shapes():
    cursor = keyset_svc._encode_cursor(_sample_cursor_payload(filterHash="filter-a"))
    with pytest.raises(AppException):
        keyset_svc._decode_cursor(cursor, expected_filter_hash="filter-b")


def test_t2_cursor_rejects_payload_tampering_and_malformed_base64():
    cursor = keyset_svc._encode_cursor(_sample_cursor_payload())
    body, signature = cursor.split(".", 1)
    replacement = "A" if body[0] != "A" else "B"
    tampered = replacement + body[1:] + "." + signature

    with pytest.raises(AppException):
        keyset_svc._decode_cursor(tampered, expected_filter_hash="abc123")
    with pytest.raises(AppException):
        keyset_svc._decode_cursor("%%%%.%%%%", expected_filter_hash="abc123")


def test_t2_cursor_rejects_invalid_count_snapshot_as_validation_error():
    cursor = keyset_svc._encode_cursor(_sample_cursor_payload(statusCounts={"PENDING": "bad"}))
    with pytest.raises(AppException):
        keyset_svc._decode_cursor(cursor, expected_filter_hash="abc123")


def test_t2_keyset_reader_has_no_offset_and_counts_only_first_page_contract():
    source = inspect.getsource(keyset_svc.list_continuous)
    module_source = inspect.getsource(keyset_svc)

    assert ".offset(" not in module_source
    assert ".limit(size + 1)" in source
    assert "if first_page:" in source
    assert "_first_page_counts(" in source
    assert "due_bucket.asc()" in source
    assert "UnifiedTodo.due_at.asc()" in source
    assert "UnifiedTodo.id.desc()" in source
    assert '"filterHash"' in module_source
    assert '"asOf"' in module_source
    assert '"dueBucket"' in module_source
    assert '"dueAt"' in module_source
    assert '"id"' in module_source
    assert "hmac.compare_digest" in module_source


def test_t2_keyset_reader_reuses_canonical_todo_projection_not_third_route_authority():
    source = inspect.getsource(keyset_svc)
    assert "todo_svc._visibility_cond" in source
    assert "todo_svc._todo_dict" in source
    assert "resolve_todo_route" not in source
    assert "message_action_registry" not in source
    assert "mobile_action_service" not in source


def test_t2_read_facade_forwards_cursor_and_projects_only_current_page(monkeypatch):
    seen = {}
    monkeypatch.setattr(read_svc.teacher_guard, "_require_teacher", lambda user: user)

    def fake_continuous(user, **kwargs):
        seen.update(kwargs)
        return {
            "items": [],
            "total": 21,
            "pageSize": 20,
            "nextCursor": "next-token",
            "hasMore": True,
            "statusCounts": {"PENDING": 21},
            "filterHash": "hash",
            "asOf": "2026-08-20T00:00:00.000000",
        }

    monkeypatch.setattr(read_svc.keyset_svc, "list_continuous", fake_continuous)
    result = read_svc.list_continuous(
        {"userId": "7", "userType": "TEACHER"},
        status="PENDING",
        todo_type="LEAVE",
        cursor="cursor-token",
        page_size=20,
    )

    assert seen == {
        "status": "PENDING",
        "todo_type": "LEAVE",
        "cursor": "cursor-token",
        "page_size": 20,
    }
    assert result["nextCursor"] == "next-token"
    assert result["hasMore"] is True


def test_t2_teacher_mobile_exposes_additive_continuous_route_without_breaking_t1_route():
    source = inspect.getsource(todos_api)
    helper = inspect.getsource(todos_api._teacher_v3_continuous)

    assert '@router.get("/todos",' in source
    assert '@router.get("/todos/continuous",' in source
    assert "_teacher_v3_continuous" in source
    assert "cursor: Optional[str]" in source
    assert 'next_cursor=data.get("nextCursor")' in helper
    assert 'status_counts=data.get("statusCounts")' in helper
    assert 'query_fingerprint=data.get("filterHash")' in helper
    assert 'page["hasMore"]' in helper
    assert 'page["asOf"]' in helper
