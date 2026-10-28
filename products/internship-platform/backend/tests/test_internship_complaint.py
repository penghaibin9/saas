"""P4 §5.3 · 企业投诉：受理状态机 + 转风险(双向链接) + 联系方式按角色脱敏 + 越权。"""
from __future__ import annotations

TID = 1000000000000000001
INT = "/api/v1/internship/complaints"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _tok(role):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{role}", "realName": role, "userType": "TEACHER", "tid": "x",
        "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"})}


def _student():
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-s", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID, batch_name="投诉测试批次", batch_no="CPL-BATCH-01",
            status="RUNNING", planned_count=10,
        )
        db.add(batch); db.flush()
        s = StudentProfile(tenant_id=TID, student_no="CPL-S", real_name="投诉学生",
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(s); db.flush()
        r = InternshipRecord(tenant_id=TID, student_id=s.id, batch_id=batch.id, advisor_name="刘强",
                             enterprise_name="投诉企业", position_name="实习生", status="ONBOARD")
        db.add(r); db.flush()
        db.commit()
        return {"student_id": s.id, "rec_id": r.id, "batch_id": batch.id}
    finally:
        db.close()


def _mk(ids, contact="13800001111"):
    return {"source": "STUDENT", "targetType": "ENTERPRISE", "studentId": str(ids["student_id"]),
            "batchId": str(ids["batch_id"]),
            "category": "拖欠实习补贴", "severity": "HIGH", "content": "企业未按约定发放实习补贴，多次沟通无果",
            "complainantContact": contact}


def _batch_q(ids):
    return {"batchId": str(ids["batch_id"])}


def _bad(resp):
    return resp.status_code in (400, 409) or resp.json().get("code") not in (0, None)


def test_create_and_full_flow(client, db_mode):
    ids = _seed(db_mode)
    a = _admin(client)
    c = client.post(INT, json=_mk(ids), headers=a)
    assert c.status_code == 200 and c.json()["data"]["status"] == "RECEIVED"
    assert c.json()["data"]["complaintNo"].startswith("CPL-")
    cid = c.json()["data"]["id"]
    assert client.post(f"{INT}/{cid}/transition", json={"action": "ACCEPT", "ownerName": "王老师"}, headers=a).json()["data"]["status"] == "ACCEPTED"
    assert client.post(f"{INT}/{cid}/transition", json={"action": "INVESTIGATE"}, headers=a).json()["data"]["status"] == "INVESTIGATING"
    r = client.post(f"{INT}/{cid}/transition", json={"action": "RESOLVE", "conclusion": "已督促企业补发补贴并道歉"}, headers=a)
    assert r.json()["data"]["status"] == "RESOLVED"
    assert client.post(f"{INT}/{cid}/followup", json={"result": "学生确认已收到补贴"}, headers=a).json()["data"]["followupResult"]


def test_resolve_requires_conclusion(client, db_mode):
    ids = _seed(db_mode)
    a = _admin(client)
    cid = client.post(INT, json=_mk(ids), headers=a).json()["data"]["id"]
    client.post(f"{INT}/{cid}/transition", json={"action": "ACCEPT"}, headers=a)
    client.post(f"{INT}/{cid}/transition", json={"action": "INVESTIGATE"}, headers=a)
    assert client.post(f"{INT}/{cid}/transition", json={"action": "RESOLVE", "conclusion": "x"}, headers=a).status_code == 400


def test_to_risk_and_no_double(client, db_mode):
    ids = _seed(db_mode)
    a = _admin(client)
    cid = client.post(INT, json=_mk(ids), headers=a).json()["data"]["id"]
    client.post(f"{INT}/{cid}/transition", json={"action": "ACCEPT"}, headers=a)
    r = client.post(f"{INT}/{cid}/to-risk", headers=a)
    assert r.status_code == 200 and r.json()["data"]["riskId"]
    assert _bad(client.post(f"{INT}/{cid}/to-risk", headers=a))


def test_sensitive_mask_by_role(client, db_mode):
    ids = _seed(db_mode)
    a = _admin(client)
    cid = client.post(INT, json=_mk(ids, "13800001111"), headers=a).json()["data"]["id"]
    ad = client.get(f"{INT}/{cid}", headers=a).json()["data"]
    assert ad["complainantContact"] == "13800001111" and ad["complainantContactMasked"] is False
    au = client.get(f"{INT}/{cid}", headers=_tok("SECURITY_AUDITOR")).json()["data"]
    assert au["complainantContactMasked"] is True and "****" in au["complainantContact"]


def test_invalid_transition(client, db_mode):
    ids = _seed(db_mode)
    a = _admin(client)
    cid = client.post(INT, json=_mk(ids), headers=a).json()["data"]["id"]
    assert _bad(client.post(f"{INT}/{cid}/transition", json={"action": "INVESTIGATE"}, headers=a))


def test_list_requires_batch_id(client, db_mode):
    _seed(db_mode)
    miss = client.get(INT, headers=_admin(client)).json()
    assert miss["code"] != 0
    assert "batchId" in (miss.get("message") or "")


def test_auditor_readonly_cannot_intake(client, db_mode):
    ids = _seed(db_mode)
    # 督导有 complaint.view 但无 intake → 列表可读、登记 403
    assert client.get(INT, headers=_tok("SECURITY_AUDITOR"), params=_batch_q(ids)).status_code == 200
    assert client.post(INT, json=_mk(ids), headers=_tok("SECURITY_AUDITOR")).status_code == 403


def test_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    assert client.get(INT, headers=_student(), params=_batch_q(ids)).status_code == 403


def test_content_required(client, db_mode):
    r = client.post(INT, json={"source": "STUDENT", "content": "短", "severity": "LOW"}, headers=_admin(client))
    assert _bad(r)
