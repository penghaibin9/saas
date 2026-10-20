"""P4 §5.2 · 巡访计划：状态机(DRAFT→PUBLISHED→IN_PROGRESS→COMPLETED) + owner 数据范围 + 越权。"""
from __future__ import annotations

TID = 1000000000000000001
INT = "/api/v1/internship/visit-plans"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _mentor(name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER", "tid": "x",
        "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student():
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-s", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _mk(objective="检查实习安全与在岗情况"):
    return {"enterpriseName": "巡访测试企业", "objective": objective, "planDate": "2026-08-01",
            "method": "ONSITE", "studentScope": "甲,乙"}


def _bad(resp):
    return resp.status_code in (400, 409) or resp.json().get("code") not in (0, None)


def test_create_and_full_flow(client, db_mode):
    a = _admin(client)
    p = client.post(INT, json=_mk(), headers=a)
    assert p.status_code == 200 and p.json()["data"]["status"] == "DRAFT"
    pid = p.json()["data"]["id"]
    assert client.post(f"{INT}/{pid}/transition", json={"action": "PUBLISH"}, headers=a).json()["data"]["status"] == "PUBLISHED"
    assert client.post(f"{INT}/{pid}/transition", json={"action": "START"}, headers=a).json()["data"]["status"] == "IN_PROGRESS"
    done = client.post(f"{INT}/{pid}/transition", json={"action": "COMPLETE"}, headers=a)
    assert done.json()["data"]["status"] == "COMPLETED" and done.json()["data"]["completedAt"]


def test_invalid_transition_draft_to_start(client, db_mode):
    a = _admin(client)
    pid = client.post(INT, json=_mk(), headers=a).json()["data"]["id"]
    # DRAFT 不可直接 START（须先 PUBLISH）
    assert _bad(client.post(f"{INT}/{pid}/transition", json={"action": "START"}, headers=a))


def test_cancel_requires_reason(client, db_mode):
    a = _admin(client)
    pid = client.post(INT, json=_mk(), headers=a).json()["data"]["id"]
    assert client.post(f"{INT}/{pid}/transition", json={"action": "CANCEL", "reason": "x"}, headers=a).status_code == 400
    r = client.post(f"{INT}/{pid}/transition", json={"action": "CANCEL", "reason": "企业临时不便接待"}, headers=a)
    assert r.json()["data"]["status"] == "CANCELLED"


def test_completed_not_editable(client, db_mode):
    a = _admin(client)
    pid = client.post(INT, json=_mk(), headers=a).json()["data"]["id"]
    for act in ("PUBLISH", "START", "COMPLETE"):
        client.post(f"{INT}/{pid}/transition", json={"action": act}, headers=a)
    assert _bad(client.put(f"{INT}/{pid}", json={"objective": "改"}, headers=a))


def test_owner_scope(client, db_mode):
    a = _admin(client)
    client.post(INT, json=_mk("管理员建的计划"), headers=a)          # owner = school_admin realName
    client.post(INT, json=_mk("刘强建的计划"), headers=_mentor("刘强"))  # owner = 刘强
    liu = client.get(INT, headers=_mentor("刘强")).json()["data"]
    assert liu["total"] == 1 and liu["items"][0]["objective"] == "刘强建的计划"
    assert client.get(INT, headers=a).json()["data"]["total"] == 2


def test_student_forbidden(client, db_mode):
    assert client.get(INT, headers=_student()).status_code == 403


def test_detail_and_audit(client, db_mode):
    a = _admin(client)
    pid = client.post(INT, json=_mk(), headers=a).json()["data"]["id"]
    client.post(f"{INT}/{pid}/transition", json={"action": "PUBLISH"}, headers=a)
    d = client.get(f"{INT}/{pid}", headers=a).json()["data"]
    actions = {t["action"] for t in d["auditTrail"]}
    assert "CREATE" in actions and "PUBLISH" in actions
