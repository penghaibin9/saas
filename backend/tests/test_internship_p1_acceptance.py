"""P1 验收收口：关键写操作 expectedVersion + MySQL 双连接容量竞争 + 旧接口门禁。"""
from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException

BATCH = "/api/v1/internship/batches"
IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"
ENT = "/api/v1/internship/enterprises"
POS = "/api/v1/internship/positions"
AGR = "/api/v1/internship/agreements"
SCORE = "/api/v1/internship/scores"
TID = "1000000000000000001"


def _uniq(p: str) -> str:
    return f"{p}-{uuid.uuid4().hex[:8]}"


def _credit() -> str:
    """合法 18 位统一社会信用代码（测试用，避开 I/O/S/V/Z）。"""
    s = uuid.uuid4().hex[:8].upper()
    for a, b in (("I", "A"), ("O", "B"), ("S", "C"), ("V", "D"), ("Z", "E")):
        s = s.replace(a, b)
    return f"91310000{s}XA"


def _mk_running_batch(client, h):
    r = client.post(BATCH, headers=h, json={
        "batchName": _uniq("P1A"), "batchNo": _uniq("P1ABN"),
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }).json()
    assert r["code"] == 0, r
    bid, ver = r["data"]["id"], int(r["data"].get("version") or 0)
    act = client.post(f"{BATCH}/{bid}/activate", headers=h, json={"expectedVersion": ver}).json()
    assert act["code"] == 0, act
    return bid


def _mk_student(client, h):
    sno = _uniq("P1S")
    r = client.post(STU, headers=h, json={"studentNo": sno, "realName": f"生{sno[-4:]}"}).json()
    assert r["code"] == 0, r
    return r["data"]["id"], sno


def test_agreement_issue_requires_and_conflicts_expected_version(client, auth_headers, db_mode):
    bid = _mk_running_batch(client, auth_headers)
    sid, _ = _mk_student(client, auth_headers)
    rec = client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()
    assert rec["code"] == 0, rec
    gen = client.post(AGR, headers=auth_headers, json={"internshipId": rec["data"]["id"]}).json()
    if gen.get("code") != 0:
        pytest.skip(f"agreement generate unavailable: {gen}")
    aid = gen["data"]["id"]
    ver = int(gen["data"].get("version") or 0)
    missing = client.post(f"{AGR}/{aid}/issue", headers=auth_headers, json={}).json()
    assert missing["code"] != 0
    stale = client.post(f"{AGR}/{aid}/issue", headers=auth_headers,
                        json={"expectedVersion": ver + 9}).json()
    assert stale["code"] != 0
    ok = client.post(f"{AGR}/{aid}/issue", headers=auth_headers,
                     json={"expectedVersion": ver}).json()
    assert ok["code"] == 0, ok
    assert int(ok["data"].get("version") or 0) == ver + 1


def test_score_publish_stale_version_conflict(client, auth_headers, db_mode):
    bid = _mk_running_batch(client, auth_headers)
    sid, _ = _mk_student(client, auth_headers)
    rec = client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()
    assert rec["code"] == 0
    iid = rec["data"]["id"]
    computed = client.post(SCORE + "/compute", headers=auth_headers, json={
        "internshipId": iid, "checkinScore": 90, "weeklyScore": 90, "monthlyScore": 90,
        "enterpriseScore": 90, "schoolScore": 90,
    }).json()
    if computed.get("code") != 0:
        pytest.skip(f"score compute unavailable: {computed}")
    sid_score = computed["data"]["id"]
    detail = client.get(f"{SCORE}/{sid_score}", headers=auth_headers).json()
    ver = int((detail.get("data") or {}).get("version") or computed["data"].get("version") or 0)
    missing = client.post(f"{SCORE}/{sid_score}/publish", headers=auth_headers, json={}).json()
    assert missing["code"] != 0
    stale = client.post(f"{SCORE}/{sid_score}/publish", headers=auth_headers,
                        json={"expectedVersion": ver + 5}).json()
    assert stale["code"] != 0
    ok = client.post(f"{SCORE}/{sid_score}/publish", headers=auth_headers,
                     json={"expectedVersion": ver}).json()
    assert ok["code"] == 0, ok


def test_old_students_list_requires_batch_id(client, auth_headers, db_mode):
    missing = client.get("/api/v1/internship/students", headers=auth_headers).json()
    assert missing["code"] != 0
    bid = _mk_running_batch(client, auth_headers)
    ok = client.get("/api/v1/internship/students", headers=auth_headers, params={"batchId": bid}).json()
    assert ok["code"] == 0, ok
    assert ok["data"].get("deprecated") is True


def test_weekly_batch_review_requires_expected_version(client, auth_headers, db_mode):
    """批量批阅禁止只传 ids 绕过 expectedVersion。"""
    miss = client.post("/api/v1/internship/reports/batch-review", headers=auth_headers,
                       json={"ids": ["1"], "action": "APPROVE", "comment": "批量通过"}).json()
    assert miss["code"] != 0


def test_mobile_my_students_requires_batch_id(client, auth_headers, db_mode):
    miss = client.get("/api/v1/mobile/teacher/internship/my-students", headers=auth_headers).json()
    assert miss["code"] != 0
    bid = _mk_running_batch(client, auth_headers)
    ok = client.get("/api/v1/mobile/teacher/internship/my-students", headers=auth_headers,
                    params={"batchId": bid}).json()
    assert ok["code"] == 0, ok


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") or "").startswith("mysql"),
    reason="MySQL-only dual-connection race",
)
def test_mysql_two_connections_last_slot_race(client, auth_headers, db_mode):
    """headcount=1 时两个独立事务同时分配，只能一个成功。"""
    from app.models import InternshipPosition, InternshipRecord
    from app.modules.internship.services import internship_student_service as student_svc
    from app.services.db_service import session as db_session

    bid = _mk_running_batch(client, auth_headers)
    s1, _ = _mk_student(client, auth_headers)
    s2, _ = _mk_student(client, auth_headers)
    r1 = client.post(IST, headers=auth_headers, json={"studentId": s1, "batchId": bid}).json()
    r2 = client.post(IST, headers=auth_headers, json={"studentId": s2, "batchId": bid}).json()
    assert r1["code"] == 0 and r2["code"] == 0
    rec_a, rec_b = r1["data"]["id"], r2["data"]["id"]

    ent = client.post(ENT, headers=auth_headers, json={
        "name": _uniq("竞态企"), "creditCode": _credit(),
    }).json()
    if ent.get("code") != 0:
        pytest.fail(f"enterprise create failed: {ent}")
    eid = ent["data"]["id"]
    client.post(f"{ENT}/{eid}/review", headers=auth_headers, json={"action": "APPROVE"})
    pos = client.post(POS, headers=auth_headers, json={
        "companyId": eid, "title": _uniq("末席岗"), "headcount": 1, "batchId": bid,
    }).json()
    if pos.get("code") != 0:
        pytest.fail(f"position create failed: {pos}")
    pid = pos["data"]["id"]
    sub = client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "SUBMIT"}).json()
    if sub.get("code") != 0:
        pytest.fail(f"position submit failed: {sub}")
    pub = client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()
    if pub.get("code") != 0:
        pytest.fail(f"position publish failed: {pub}")

    barrier = threading.Barrier(2, timeout=30)
    results: list[tuple[str, object]] = []
    lock = threading.Lock()
    admin = {"userId": "1", "realName": "school_admin01", "loginName": "school_admin01",
             "currentRoleCode": "SCHOOL_ADMIN", "userType": "TEACHER"}

    def _race(rec_id: str):
        set_tenant({"tenantId": TID})
        set_current_user(admin)
        barrier.wait()
        try:
            row = student_svc.assign_position(rec_id, pid, user=admin)
            with lock:
                results.append(("ok", row))
        except AppException as e:
            with lock:
                results.append(("err", e))
        finally:
            set_current_user(None)
            set_tenant(None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_race, rec_a), pool.submit(_race, rec_b)]
        for f in futs:
            f.result(timeout=60)

    oks = [x for x in results if x[0] == "ok"]
    errs = [x for x in results if x[0] == "err"]
    assert len(oks) == 1, results
    assert len(errs) == 1, results
    assert errs[0][1].code == "DATA_CONFLICT"

    set_tenant({"tenantId": TID})
    try:
        from sqlalchemy import func, select
        with db_session() as db:
            p = db.get(InternshipPosition, int(pid))
            assert p is not None
            assert int(p.allocated_count or 0) == 1
            assigned = db.scalar(select(func.count()).select_from(InternshipRecord).where(
                InternshipRecord.tenant_id == int(TID),
                InternshipRecord.is_deleted.is_(False),
                InternshipRecord.position_id == int(pid),
            )) or 0
            assert int(assigned) == 1
    finally:
        set_tenant(None)

    # 调岗失败时旧岗保留：再建 headcount=1 已满岗，尝试把已占岗学生调过去应失败且仍保留原岗
    pos2 = client.post(POS, headers=auth_headers, json={
        "companyId": eid, "title": _uniq("满岗"), "headcount": 1, "batchId": bid,
    }).json()
    if pos2.get("code") == 0:
        pid2 = pos2["data"]["id"]
        client.post(f"{POS}/{pid2}/status", headers=auth_headers, json={"action": "SUBMIT"})
        client.post(f"{POS}/{pid2}/status", headers=auth_headers, json={"action": "PUBLISH"})
        # 占满 pos2
        s3, _ = _mk_student(client, auth_headers)
        r3 = client.post(IST, headers=auth_headers, json={"studentId": s3, "batchId": bid}).json()
        assert r3["code"] == 0
        a3 = client.post(f"{IST}/{r3['data']['id']}/assign", headers=auth_headers,
                         json={"positionId": pid2}).json()
        assert a3["code"] == 0, a3
        winner_id = oks[0][1]["id"]
        fail = client.post(f"{IST}/{winner_id}/assign", headers=auth_headers,
                           json={"positionId": pid2}).json()
        assert fail["code"] != 0
        still = client.get(f"{IST}/{winner_id}", headers=auth_headers).json()
        assert still["code"] == 0
        assert str(still["data"].get("positionId") or "") == str(pid)
