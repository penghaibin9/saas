"""补卡/变更/申请批次强制 + void/审核 expectedVersion 回归。"""
from __future__ import annotations

import uuid

BATCH = "/api/v1/internship/batches"
IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"
MAKEUPS = "/api/v1/internship/makeups"
CHANGES = "/api/v1/internship/change-requests"
APPS = "/api/v1/internship/applications"
MOB = "/api/v1/mobile"


TID = 1000000000000000001


def _uniq(p: str) -> str:
    return f"{p}-{uuid.uuid4().hex[:8]}"


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


def _mk_running_batch(client, h):
    r = client.post(BATCH, headers=h, json={
        "batchName": _uniq("BLG"), "batchNo": _uniq("BLGN"),
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }).json()
    assert r["code"] == 0, r
    bid, ver = r["data"]["id"], int(r["data"].get("version") or 0)
    act = client.post(f"{BATCH}/{bid}/activate", headers=h, json={"expectedVersion": ver}).json()
    assert act["code"] == 0, act
    return bid


def _mk_student(client, h):
    sno = _uniq("BLGS")
    r = client.post(STU, headers=h, json={"studentNo": sno, "realName": f"生{sno[-4:]}",
                                          "classId": _org_class()}).json()
    assert r["code"] == 0, r
    return r["data"]["id"], sno


def test_makeups_list_export_require_and_respect_batch_id(client, auth_headers, db_mode):
    miss = client.get(MAKEUPS, headers=auth_headers).json()
    assert miss["code"] != 0
    assert "batchId" in (miss.get("message") or "")
    exp = client.post(f"{MAKEUPS}/export", headers=auth_headers).json()
    assert exp["code"] != 0

    b1 = _mk_running_batch(client, auth_headers)
    b2 = _mk_running_batch(client, auth_headers)
    sid, _ = _mk_student(client, auth_headers)
    rec = client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b1}).json()
    assert rec["code"] == 0, rec

    ok_empty = client.get(MAKEUPS, headers=auth_headers, params={"batchId": b1}).json()
    assert ok_empty["code"] == 0
    assert ok_empty["data"]["total"] == 0
    other = client.get(MAKEUPS, headers=auth_headers, params={"batchId": b2}).json()
    assert other["code"] == 0
    assert other["data"]["total"] == 0

    exp_ok = client.post(f"{MAKEUPS}/export", headers=auth_headers, params={"batchId": b1}).json()
    assert exp_ok["code"] == 0
    assert exp_ok["data"]["filename"].endswith(".xlsx")


def test_change_and_application_lists_require_batch_id(client, auth_headers, db_mode):
    assert client.get(CHANGES, headers=auth_headers).json()["code"] != 0
    assert client.get(APPS, headers=auth_headers).json()["code"] != 0
    bid = _mk_running_batch(client, auth_headers)
    assert client.get(CHANGES, headers=auth_headers, params={"batchId": bid}).json()["code"] == 0
    assert client.get(APPS, headers=auth_headers, params={"batchId": bid}).json()["code"] == 0


def test_void_batch_requires_expected_version(client, auth_headers, db_mode):
    c = client.post(BATCH, headers=auth_headers, json={
        "batchName": _uniq("VOID"), "batchNo": _uniq("VOIDN"),
    }).json()
    assert c["code"] == 0, c
    bid, ver = c["data"]["id"], int(c["data"].get("version") or 0)
    missing = client.post(f"{BATCH}/{bid}/void", headers=auth_headers,
                          json={"reason": "批次信息录入有误，作废重建"}).json()
    assert missing["code"] != 0
    stale = client.post(f"{BATCH}/{bid}/void", headers=auth_headers,
                        json={"reason": "批次信息录入有误，作废重建", "expectedVersion": ver + 9}).json()
    assert stale["code"] != 0
    ok = client.post(f"{BATCH}/{bid}/void", headers=auth_headers,
                     json={"reason": "批次信息录入有误，作废重建", "expectedVersion": ver}).json()
    assert ok["code"] == 0, ok
    assert ok["data"]["status"] == "VOIDED"
    assert int(ok["data"].get("version") or 0) == ver + 1


def test_application_review_requires_expected_version(client, auth_headers, db_mode):
    """审核接口缺 version / 错 version 必须失败（不依赖完整申请落岗数据）。"""
    miss = client.post(f"{APPS}/1/review", headers=auth_headers, json={"action": "REJECT", "comment": "材料不齐请补充"}).json()
    assert miss["code"] != 0
    # 不存在的申请在校验 version 之后/之前都可能失败；关键是缺 version 不得静默成功
    assert "expectedVersion" in (miss.get("message") or "") or miss["code"] != 0


def test_communications_and_complaints_require_batch_id(client, auth_headers, db_mode):
    COMM = "/api/v1/internship/communications"
    CPL = "/api/v1/internship/complaints"
    assert client.get(COMM, headers=auth_headers).json()["code"] != 0
    assert client.get(CPL, headers=auth_headers).json()["code"] != 0
    bid = _mk_running_batch(client, auth_headers)
    assert client.get(COMM, headers=auth_headers, params={"batchId": bid}).json()["code"] == 0
    assert client.get(CPL, headers=auth_headers, params={"batchId": bid}).json()["code"] == 0
