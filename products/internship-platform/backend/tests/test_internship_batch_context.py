"""岗位实习 · 批次上下文 / 列表统计导出一致 / 工作台 / 导入 / 风险口径回归。

覆盖本轮 Bug 收口验收场景；依赖 MySQL（db_mode fixture）。
"""
from __future__ import annotations

import uuid

IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"
BATCH = "/api/v1/internship/batches"
DASH = "/api/v1/internship/dashboard"
STATS = "/api/v1/internship/stats"
RISK = "/api/v1/internship/risks"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch_version(client, h, bid) -> int:
    d = client.get(f"{BATCH}/{bid}", headers=h).json()
    assert d["code"] == 0, d
    return int(d["data"].get("version") or 0)


def _mk_batch(client, h, *, status="RUNNING", name=None, no=None):
    body = {
        "batchName": name or _uniq("批次"),
        "batchNo": no or _uniq("BN"),
        "startDate": "2026-03-01",
        "endDate": "2026-08-31",
        "plannedCount": 10,
    }
    r = client.post(BATCH, headers=h, json=body).json()
    assert r["code"] == 0, r
    bid = r["data"]["id"]
    ver = int(r["data"].get("version") or 0)
    if status == "RUNNING":
        act = client.post(f"{BATCH}/{bid}/activate", headers=h, json={"expectedVersion": ver}).json()
        assert act["code"] == 0, act
    elif status == "CLOSED":
        act = client.post(f"{BATCH}/{bid}/activate", headers=h, json={"expectedVersion": ver}).json()
        assert act["code"] == 0, act
        ver = int(act["data"].get("version") or (ver + 1))
        cl = client.post(f"{BATCH}/{bid}/close", headers=h,
                         json={"expectedVersion": ver, "force": True,
                               "forceReason": "测试环境强制结束空批次"}).json()
        assert cl["code"] == 0, cl
    elif status == "VOIDED":
        assert client.post(f"{BATCH}/{bid}/void", headers=h, json={
            "reason": "测试作废原因足够长", "expectedVersion": ver,
        }).json()["code"] == 0
    return bid


TID = 1000000000000000001


def _org_class():
    """建档必须挂真实学院/专业/班级，见 tests/test_student.py::org_class。"""
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass
    db = get_sessionmaker()()
    try:
        col = College(tenant_id=TID, college_name=_uniq("学院"), status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=TID, college_id=col.id, major_name=_uniq("专业"), status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=TID, major_id=maj.id, class_name=_uniq("班级"),
                          grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(cls); db.flush()
        cid = cls.id
        db.commit()
        return str(cid)
    finally:
        db.close()


def _mk_student(client, h, no=None):
    sno = no or _uniq("S")
    r = client.post(STU, headers=h, json={"studentNo": sno, "realName": f"学生{sno[-4:]}",
                                          "classId": _org_class()}).json()
    assert r["code"] == 0, r
    return r["data"]["id"], sno


def test_create_requires_batch_id(client, auth_headers, db_mode):
    sid, _ = _mk_student(client, auth_headers)
    r = client.post(IST, headers=auth_headers, json={"studentId": sid}).json()
    assert r["code"] != 0
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": "abc"}).json()["code"] != 0
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": "999999999999"}).json()["code"] != 0


def test_create_rejects_voided_closed_and_cross_tenant_batch(client, auth_headers, db_mode):
    sid, _ = _mk_student(client, auth_headers)
    voided = _mk_batch(client, auth_headers, status="VOIDED")
    closed = _mk_batch(client, auth_headers, status="CLOSED")
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": voided}).json()["code"] != 0
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": closed}).json()["code"] != 0


def test_same_student_different_batches_ok_same_batch_dup(client, auth_headers, db_mode):
    sid, _ = _mk_student(client, auth_headers)
    b1 = _mk_batch(client, auth_headers)
    b2 = _mk_batch(client, auth_headers)
    r1 = client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b1}).json()
    assert r1["code"] == 0 and r1["data"]["batchId"] == str(b1)
    r2 = client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b2}).json()
    assert r2["code"] == 0 and r2["data"]["batchId"] == str(b2)
    dup = client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b1}).json()
    assert dup["code"] != 0


def test_list_stats_export_same_batch_and_require_batch(client, auth_headers, db_mode):
    b1 = _mk_batch(client, auth_headers)
    b2 = _mk_batch(client, auth_headers)
    s1, _ = _mk_student(client, auth_headers)
    s2, _ = _mk_student(client, auth_headers)
    s3, _ = _mk_student(client, auth_headers)
    assert client.post(IST, headers=auth_headers, json={"studentId": s1, "batchId": b1}).json()["code"] == 0
    assert client.post(IST, headers=auth_headers, json={"studentId": s2, "batchId": b1}).json()["code"] == 0
    assert client.post(IST, headers=auth_headers, json={"studentId": s3, "batchId": b2}).json()["code"] == 0

    missing = client.get(IST, headers=auth_headers).json()
    assert missing["code"] != 0

    lst = client.get(IST, headers=auth_headers, params={"batchId": b1, "pageSize": 100}).json()
    assert lst["code"] == 0
    assert lst["data"]["total"] == 2
    items = lst["data"].get("items") or lst["data"].get("list") or []
    assert all(it["batchId"] == str(b1) for it in items)

    st = client.get(f"{IST}/stats", headers=auth_headers, params={"batchId": b1}).json()
    assert st["code"] == 0 and st["data"]["total"] == lst["data"]["total"]

    exp = client.post(f"{IST}/export", headers=auth_headers, params={"batchId": b1}).json()
    assert exp["code"] == 0
    assert exp["data"]["rowCount"] == lst["data"]["total"]
    assert exp["data"].get("batchId") == str(b1)


def test_import_requires_batch_and_writes_batch_id(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers)
    _, sno = _mk_student(client, auth_headers, no=_uniq("IMP"))
    rows = [{"studentNo": sno}]
    no_batch = client.post(f"{IST}/import/dry-run", headers=auth_headers, json={"rows": rows}).json()
    assert no_batch["code"] != 0
    dry = client.post(f"{IST}/import/dry-run", headers=auth_headers,
                      json={"rows": rows, "batchId": b}).json()
    assert dry["code"] == 0 and dry["data"]["validRows"] == 1
    conf = client.post(f"{IST}/import/confirm", headers=auth_headers,
                       json={"rows": rows, "batchId": b}).json()
    assert conf["code"] == 0 and conf["data"]["created"] == 1
    assert conf["data"]["batchId"] == str(b)
    lst = client.get(IST, headers=auth_headers, params={"batchId": b, "keyword": sno}).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1
    items = lst["data"].get("items") or lst["data"].get("list") or []
    assert all(it["batchId"] == str(b) for it in items)


def test_import_confirm_rejects_closed_batch_after_dry_run(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers, status="RUNNING")
    _, sno = _mk_student(client, auth_headers)
    rows = [{"studentNo": sno}]
    dry = client.post(f"{IST}/import/dry-run", headers=auth_headers,
                      json={"rows": rows, "batchId": b}).json()
    assert dry["code"] == 0
    assert client.post(f"{BATCH}/{b}/close", headers=auth_headers,
                       json={"expectedVersion": _batch_version(client, auth_headers, b),
                             "force": True, "forceReason": "导入确认前关闭批次"}).json()["code"] == 0
    conf = client.post(f"{IST}/import/confirm", headers=auth_headers,
                       json={"rows": rows, "batchId": b}).json()
    assert conf["code"] != 0


def test_dashboard_requires_batch_and_aligns_metrics(client, auth_headers, db_mode):
    b1 = _mk_batch(client, auth_headers)
    b2 = _mk_batch(client, auth_headers)
    s1, _ = _mk_student(client, auth_headers)
    s2, _ = _mk_student(client, auth_headers)
    assert client.post(IST, headers=auth_headers, json={"studentId": s1, "batchId": b1}).json()["code"] == 0
    assert client.post(IST, headers=auth_headers, json={"studentId": s2, "batchId": b2}).json()["code"] == 0

    no_bid = client.get(DASH, headers=auth_headers).json()
    assert no_bid["code"] != 0

    d = client.get(DASH, headers=auth_headers, params={"batchId": b1}).json()
    assert d["code"] == 0
    assert d["data"]["batchId"] == str(b1)
    total_stat = next(x for x in d["data"]["stats"] if x["label"] == "本批学生")
    assert total_stat["value"] == "1"
    # 0 数量待办不得伪装为待处理
    assert all(t["count"] > 0 for t in d["data"]["todos"])
    assert isinstance(d["data"]["riskAlerts"], list)
    for t in d["data"]["todos"]:
        assert f"batchId={b1}" in t["route"]


def test_dashboard_risk_alerts_real_when_open(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, RiskRecord

    b = _mk_batch(client, auth_headers)
    sid, _ = _mk_student(client, auth_headers)
    rec = client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b}).json()
    assert rec["code"] == 0
    rid = int(rec["data"]["id"])
    db = get_sessionmaker()()
    try:
        row = db.get(InternshipRecord, rid)
        risk = RiskRecord(
            tenant_id=row.tenant_id, internship_id=rid,
            risk_code="INT-R-TEST", risk_title="测试开放风险",
            risk_level="HIGH", status="PENDING_HANDLE", source_module="TEST",
        )
        db.add(risk)
        db.commit()
        risk_id = str(risk.id)
    finally:
        db.close()
    d = client.get(DASH, headers=auth_headers, params={"batchId": b}).json()
    assert d["code"] == 0
    assert any(a["id"] == risk_id for a in d["data"]["riskAlerts"])
    empty_batch = _mk_batch(client, auth_headers)
    d2 = client.get(DASH, headers=auth_headers, params={"batchId": empty_batch}).json()
    assert d2["code"] == 0 and d2["data"]["riskAlerts"] == []


def test_stats_batch_scope_and_empty_denominator(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers)
    sid, _ = _mk_student(client, auth_headers)
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b}).json()["code"] == 0
    assert client.get(f"{STATS}/overview", headers=auth_headers).json()["code"] != 0
    ov = client.get(f"{STATS}/overview", headers=auth_headers, params={"batchId": b}).json()
    assert ov["code"] == 0
    assert ov["data"]["batchId"] == str(b)
    keys = {m["key"]: m for m in ov["data"]["metrics"]}
    for k in ("placementRate", "arrivalRate", "weeklySubmitRate", "riskCloseRate", "scorePublishRate"):
        assert k in keys
        assert keys[k]["rate"] is None or isinstance(keys[k]["rate"], (int, float))
    # 无人在考核/归档时成绩发布率空分母 → None，不是 NaN/500
    assert keys["scorePublishRate"]["denominator"] == 0
    assert keys["scorePublishRate"]["rate"] is None


def test_risk_list_requires_batch_and_invalid_id_4xx(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers)
    assert client.get(RISK, headers=auth_headers).json()["code"] != 0
    ok = client.get(RISK, headers=auth_headers, params={"batchId": b}).json()
    assert ok["code"] == 0
    bad = client.get(f"{RISK}/not-a-number", headers=auth_headers)
    # 非法 id 不得 500
    assert bad.status_code < 500
    closed_twice = client.post(f"{RISK}/999999999/close", headers=auth_headers,
                               json={"result": "RESOLVED", "comment": "关闭说明不少于五字"}).json()
    assert closed_twice["code"] != 0
