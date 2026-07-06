"""13B-P1 学年学期/校历/节次 · 端到端（真实 DB 模式）。

T1 建学期→发布→当前学期；T2 重复学期409；T3 校历事件；T4 节次；T5 发布幂等。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _term(client, hdr, year="2026-2027", no=1):
    return client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": year, "termNo": no, "termName": f"{year}第{no}学期",
        "startDate": "2026-09-01", "endDate": "2027-01-15", "teachingWeeks": 18})


def test_t1_create_publish_current(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    tid = _term(client, hdr).json()["data"]["termId"]
    r = client.post(f"{BASE}/terms/{tid}/publish", headers=hdr).json()
    assert r["data"]["status"] == "PUBLISHED" and r["data"]["isCurrent"] is True
    cur = client.get(f"{BASE}/terms/current", headers=hdr).json()["data"]
    assert cur["termId"] == tid


def test_t2_duplicate_term_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    _term(client, hdr, "2026-2027", 1)
    assert _term(client, hdr, "2026-2027", 1).status_code == 409


def test_t3_calendar_event(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    tid = _term(client, hdr).json()["data"]["termId"]
    client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={
        "eventType": "EXAM", "startDate": "2027-01-05", "endDate": "2027-01-12", "remark": "期末考试周"})
    items = client.get(f"{BASE}/terms/{tid}/calendar", headers=hdr).json()["data"]["items"]
    assert len(items) == 1 and items[0]["eventType"] == "EXAM"


def test_t4_time_slots(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    client.post(f"{BASE}/time-slots", headers=hdr, json={"slotNo": 1, "slotName": "第一节",
                                                         "startTime": "08:00", "endTime": "08:45"})
    items = client.get(f"{BASE}/time-slots", headers=hdr).json()["data"]["items"]
    assert any(s["slotNo"] == 1 for s in items)


def test_t5_publish_idempotent_and_single_current(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    t1 = _term(client, hdr, "2026-2027", 1).json()["data"]["termId"]
    t2 = _term(client, hdr, "2026-2027", 2).json()["data"]["termId"]
    client.post(f"{BASE}/terms/{t1}/publish", headers=hdr)
    client.post(f"{BASE}/terms/{t1}/publish", headers=hdr)  # 幂等
    client.post(f"{BASE}/terms/{t2}/publish", headers=hdr)  # 切换当前
    cur = client.get(f"{BASE}/terms/current", headers=hdr).json()["data"]
    assert cur["termId"] == t2  # 仅一个当前学期
