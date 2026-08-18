"""A-W4 RED contract: File Exchange error evidence must survive persistence/export."""
from __future__ import annotations

import json
from types import SimpleNamespace


def _exchange():
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
    return exchange


class _ScalarRows:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, rows):
        self.rows = list(rows)

    def scalars(self, _stmt):
        return _ScalarRows(self.rows)


def test_error_snapshot_redacts_sensitive_raw_and_preserves_structured_resolution():
    exchange = _exchange()
    item = {
        "row": 7,
        "field": "courseCode/version",
        "code": "COURSE_STABLE_KEY_CONFLICT",
        "message": "stable key conflict",
        "raw": {
            "courseCode": "CS101",
            "version": "2",
            "phone": "13800000000",
            "idCard": "430101199001011234",
        },
        "evidence": {
            "businessKey": "CS101@v2",
            "differentFields": ["courseName"],
        },
        "howToResolve": "核对源系统版本后重新预检",
    }

    snapshot = exchange._error_snapshot(item)
    assert snapshot["courseCode"] == "CS101"
    assert snapshot["version"] == "2"
    assert "phone" not in snapshot
    assert "idCard" not in snapshot
    assert snapshot["_evidence"] == item["evidence"]
    assert snapshot["_howToResolve"] == item["howToResolve"]


def test_stored_errors_rehydrate_raw_evidence_and_resolution(monkeypatch):
    exchange = _exchange()
    monkeypatch.setattr(exchange.jobs, "_tenant_id", lambda: 1001)
    row = SimpleNamespace(
        row_no=7,
        field_code="courseCode/version",
        error_code="COURSE_STABLE_KEY_CONFLICT",
        error_message="stable key conflict",
        raw_snapshot_json={
            "courseCode": "CS101",
            "version": "2",
            "_evidence": {"businessKey": "CS101@v2", "differentFields": ["courseName"]},
            "_howToResolve": "核对源系统版本后重新预检",
        },
    )

    errors = exchange._stored_errors(_FakeDb([row]), 99)
    assert errors == [{
        "row": 7,
        "field": "courseCode/version",
        "code": "COURSE_STABLE_KEY_CONFLICT",
        "message": "stable key conflict",
        "raw": {"courseCode": "CS101", "version": "2"},
        "evidence": {"businessKey": "CS101@v2", "differentFields": ["courseName"]},
        "howToResolve": "核对源系统版本后重新预检",
    }]


def test_error_xlsx_keeps_legacy_columns_and_appends_resolution_evidence():
    exchange = _exchange()
    assert exchange._ERROR_XLSX_HEADERS[:5] == [
        "行号", "字段", "错误代码", "错误信息", "原始值(已脱敏)",
    ]
    assert exchange._ERROR_XLSX_HEADERS[5:] == ["处理建议", "证据(已脱敏)"]

    item = {
        "row": 7,
        "field": "courseCode/version",
        "code": "COURSE_STABLE_KEY_CONFLICT",
        "message": "stable key conflict",
        "raw": {"courseCode": "CS101", "version": "2"},
        "evidence": {"businessKey": "CS101@v2", "differentFields": ["courseName"]},
        "howToResolve": "核对源系统版本后重新预检",
    }
    exported = exchange._error_xlsx_row(item)
    assert exported[:4] == [7, "courseCode/version", "COURSE_STABLE_KEY_CONFLICT", "stable key conflict"]
    assert json.loads(exported[4]) == {"courseCode": "CS101", "version": "2"}
    assert exported[5] == "核对源系统版本后重新预检"
    assert json.loads(exported[6]) == {
        "businessKey": "CS101@v2",
        "differentFields": ["courseName"],
    }
