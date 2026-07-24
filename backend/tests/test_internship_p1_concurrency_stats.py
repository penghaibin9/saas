"""P1 并发 / 统计 / 导出 / 扫描回归。"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.modules.internship.services.internship_export_util import (
    SAFE_EXPORT_MAX, pack_export_meta, require_exportable,
)
from app.modules.internship.services.internship_stats_service import (
    METRIC_DEFINITIONS, METRIC_VERSION, _metric,
)

BATCH = "/api/v1/internship/batches"
STATS = "/api/v1/internship/stats"
IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_stats_rate_integrity_and_empty_denominator():
    empty = _metric("arrivalRate", "到岗率", 0, 0, 90)
    assert empty["rate"] is None and empty["anomaly"] is False
    anomaly = _metric("arrivalRate", "到岗率", 2, 1, 90)
    assert anomaly["rate"] is None and anomaly["anomaly"] is True
    assert METRIC_VERSION == "internship-stats-v1"
    assert {"arrivalRate", "weeklySubmitRate", "placementRate"} <= set(METRIC_DEFINITIONS)


def test_export_contract_rejects_oversized_result():
    assert pack_export_meta(3, 3)["truncated"] is False
    try:
        require_exportable(SAFE_EXPORT_MAX + 1)
    except Exception as exc:  # AppException has project-specific inheritance
        assert "安全上限" in str(exc)
    else:
        raise AssertionError("oversized export must be rejected")


def test_batch_null_scan_counts_before_sampling():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "internship_batch_null_scan.py").read_text(encoding="utf-8")
    assert "SELECT COUNT(*)" in source
    assert "nullBatchHasMore" in source
    ref = (Path(__file__).resolve().parents[1] / "scripts" / "internship_referential_scan.py").read_text(encoding="utf-8")
    assert "wroteData" in ref and "SELECT COUNT(*)" in ref


def test_batch_activate_requires_expected_version(client, auth_headers, db_mode):
    created = client.post(BATCH, headers=auth_headers, json={
        "batchName": _uniq("P1批"), "batchNo": _uniq("P1BN"),
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 3,
    }).json()
    assert created["code"] == 0
    bid = created["data"]["id"]
    ver = int(created["data"].get("version") or 0)
    missing = client.post(f"{BATCH}/{bid}/activate", headers=auth_headers, json={}).json()
    assert missing["code"] != 0
    stale = client.post(f"{BATCH}/{bid}/activate", headers=auth_headers,
                        json={"expectedVersion": ver + 9}).json()
    assert stale["code"] != 0
    assert "冲突" in (stale.get("message") or "") or stale.get("bizCode") in (
        "DATA_CONFLICT", "APPROVAL_VERSION_CONFLICT", "VALIDATION_ERROR")
    ok = client.post(f"{BATCH}/{bid}/activate", headers=auth_headers,
                     json={"expectedVersion": ver}).json()
    assert ok["code"] == 0, ok
    assert int(ok["data"].get("version") or 0) == ver + 1


def test_stats_drilldown_matches_overview_numerator(client, auth_headers, db_mode):
    created = client.post(BATCH, headers=auth_headers, json={
        "batchName": _uniq("统计批"), "batchNo": _uniq("STBN"),
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }).json()
    bid = created["data"]["id"]
    ver = int(created["data"].get("version") or 0)
    assert client.post(f"{BATCH}/{bid}/activate", headers=auth_headers,
                       json={"expectedVersion": ver}).json()["code"] == 0
    sid = client.post(STU, headers=auth_headers, json={
        "studentNo": _uniq("PS"), "realName": "统计生"}).json()["data"]["id"]
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()["code"] == 0
    overview = client.get(f"{STATS}/overview", headers=auth_headers, params={"batchId": bid}).json()
    assert overview["code"] == 0, overview
    assert overview["data"].get("metricVersion") == METRIC_VERSION
    m = next(x for x in overview["data"]["metrics"] if x["key"] == "placementRate")
    dd = client.get(f"{STATS}/metrics/placementRate/drilldown", headers=auth_headers, params={
        "batchId": bid, "subset": "denominator", "page": 1, "pageSize": 20,
    }).json()
    assert dd["code"] == 0, dd
    assert dd["data"]["total"] == m["denominator"]
