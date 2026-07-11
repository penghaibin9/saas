"""岗位实习 · 过程报告（日报/月报/总结）+ 实习变更 + 学生企业/岗位评价。"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
INT = "/api/v1/internship"
MOB = "/api/v1/mobile"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _student(sno="PC-STU-01"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-stu-pc", "realName": "过程报告学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _mentor(name="刘强"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        s = StudentProfile(tenant_id=TID, student_no="PC-STU-01", real_name="过程学生",
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(s)
        db.flush()
        r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name="刘强",
                             enterprise_name="原企业", position_name="原岗位",
                             status="ONBOARD", risk_level="NONE")
        db.add(r)
        db.flush()
        db.commit()
        return {"rec_id": r.id, "stu_id": s.id}
    finally:
        db.close()


def test_process_report_submit_and_review(client, db_mode):
    ids = _seed(db_mode)
    content = "今" * 35
    sub = client.post(f"{MOB}/internship/process-report",
                      json={"reportType": "DAILY", "periodKey": "2026-07-10", "content": content},
                      headers=_student())
    assert sub.status_code == 200 and sub.json()["code"] == 0
    rid = sub.json()["data"]["id"]
    lst = client.get(f"{INT}/process-reports", params={"reportType": "DAILY"},
                     headers=_mentor("刘强"))
    assert lst.status_code == 200 and lst.json()["data"]["total"] >= 1
    rev = client.post(f"{INT}/process-reports/{rid}/review",
                      json={"action": "APPROVE", "comment": "良好"},
                      headers=_mentor("刘强"))
    assert rev.status_code == 200 and rev.json()["data"]["status"] == "APPROVED"


def test_change_request_apply_and_review(client, db_mode):
    _seed(db_mode)
    apply = client.post(f"{MOB}/internship/change-request",
                        json={"changeType": "CHANGE_ENTERPRISE", "reason": "企业搬迁需换单位",
                              "targetEnterpriseName": "新企业A", "targetPositionName": "新岗位B"},
                        headers=_student())
    assert apply.status_code == 200 and apply.json()["code"] == 0
    cid = apply.json()["data"]["id"]
    lst = client.get(f"{INT}/change-requests", params={"status": "PENDING"},
                     headers=_mentor("刘强"))
    assert lst.status_code == 200
    assert any(x["id"] == cid for x in lst.json()["data"]["items"])
    rev = client.post(f"{INT}/change-requests/{cid}/review",
                      json={"action": "APPROVE", "comment": "同意变更"},
                      headers=_mentor("刘强"))
    assert rev.status_code == 200 and rev.json()["data"]["status"] == "APPROVED"


def test_self_eval_enterprise_rating(client, db_mode):
    _seed(db_mode)
    body = {
        "selfSummary": "实习总结内容" * 20,
        "enterpriseRating": 4,
        "positionRating": 5,
        "enterpriseFeedback": "企业氛围好",
        "positionFeedback": "岗位匹配专业"
    }
    sub = client.post(f"{MOB}/internship/self-eval", json=body, headers=_student())
    assert sub.status_code == 200 and sub.json()["code"] == 0
    got = client.get(f"{MOB}/internship/self-eval", headers=_student())
    assert got.json()["data"]["enterpriseRating"] == 4
    assert got.json()["data"]["positionRating"] == 5
