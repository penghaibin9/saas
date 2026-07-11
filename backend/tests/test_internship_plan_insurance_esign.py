"""岗位实习 · 计划书 + 保险 + 电子签。"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
INT = "/api/v1/internship"
MOB = "/api/v1/mobile"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _student(sno="PL-STU-01"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-pl-stu", "realName": "计划学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _mentor(name="刘强"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _seed_batch(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        b = InternshipBatch(tenant_id=TID, batch_name="计划测试批次", batch_no="PL-BATCH-01",
                            status="RUNNING", planned_count=10)
        db.add(b)
        db.flush()
        s = StudentProfile(tenant_id=TID, student_no="PL-STU-01", real_name="计划学生",
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(s)
        db.flush()
        r = InternshipRecord(tenant_id=TID, student_id=s.id, batch_id=b.id, advisor_name="刘强",
                             enterprise_name="测试企业", position_name="实习生", status="ONBOARD")
        db.add(r)
        db.flush()
        db.commit()
        return {"batch_id": b.id, "rec_id": r.id}
    finally:
        db.close()


def test_plan_publish_and_ack(client, db_mode):
    ids = _seed_batch(db_mode)
    tasks = [
        {"sortOrder": 1, "name": "岗前安全培训", "requirement": "完成企业安全培训并上传证明", "deadline": "2026-08-01T23:59:00"},
        {"sortOrder": 2, "name": "首周实习日志", "requirement": "提交不少于 300 字首周总结"},
    ]
    save = client.put(f"{INT}/plans/batch/{ids['batch_id']}",
                      json={"title": "2026春季实习计划", "objectives": "提升实践能力",
                            "content": "本计划要求完成岗位实习全过程记录与总结。" * 3,
                            "tasks": tasks},
                      headers=_admin(client))
    assert save.status_code == 200 and save.json()["code"] == 0
    assert len(save.json()["data"]["tasks"]) == 2
    assert save.json()["data"]["tasks"][0]["name"] == "岗前安全培训"
    pub = client.post(f"{INT}/plans/batch/{ids['batch_id']}/publish", headers=_admin(client))
    assert pub.status_code == 200 and pub.json()["data"]["ackCount"] >= 1
    my = client.get(f"{MOB}/internship/plan", headers=_student())
    assert my.status_code == 200 and my.json()["data"]["title"]
    assert len(my.json()["data"]["tasks"]) == 2
    ack = client.post(f"{MOB}/internship/plan/acknowledge", headers=_student())
    assert ack.status_code == 200 and ack.json()["data"]["status"] == "ACKNOWLEDGED"


def test_plan_tasks_validation(client, db_mode):
    ids = _seed_batch(db_mode)
    bad = client.put(f"{INT}/plans/batch/{ids['batch_id']}",
                     json={"title": "计划", "content": "正文足够长正文足够长正文足够长正文足够长",
                           "tasks": [{"name": "a"}]},
                     headers=_admin(client))
    assert bad.status_code == 400 or bad.json().get("code") not in (0, None)


def test_insurance_submit_and_verify(client, db_mode):
    ids = _seed_batch(db_mode)
    sub = client.post(f"{MOB}/internship/insurance",
                      json={"policyNo": "INS-2026-001", "insurerName": "某保险公司",
                            "coverageType": "实习责任险", "effectiveDate": "2026-07-01",
                            "expiryDate": "2027-06-30"},
                      headers=_student())
    assert sub.status_code == 200 and sub.json()["data"]["status"] == "PENDING_VERIFY"
    lst = client.get(f"{INT}/insurances", params={"status": "PENDING_VERIFY"},
                     headers=_mentor("刘强"))
    assert lst.status_code == 200
    iid = lst.json()["data"]["items"][0]["id"]
    ver = client.post(f"{INT}/insurances/{iid}/verify",
                      json={"action": "APPROVE", "comment": "保单有效"},
                      headers=_mentor("刘强"))
    assert ver.status_code == 200 and ver.json()["data"]["status"] == "VERIFIED"


def test_agreement_esign_flow(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipAgreement, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        s = StudentProfile(tenant_id=TID, student_no="ES-STU-01", real_name="电子签学生",
                           current_stage="INTERNSHIP", status="ACTIVE")
        db.add(s)
        db.flush()
        r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name="刘强",
                             enterprise_name="E", position_name="P", status="ONBOARD")
        db.add(r)
        db.flush()
        a = InternshipAgreement(tenant_id=TID, internship_id=r.id, student_id=s.id,
                                status="PENDING_STUDENT", rendered_body="协议正文")
        db.add(a)
        db.flush()
        aid = a.id
        db.commit()
    finally:
        db.close()
    start = client.post(f"{INT}/agreements/{aid}/esign/start", headers=_mentor("刘强"))
    assert start.status_code == 200 and start.json()["data"]["esignStatus"] == "PENDING"
    stu = _student("ES-STU-01")
    s1 = client.post(f"{MOB}/internship/agreements/{aid}/esign/sign", headers=stu)
    assert s1.status_code == 200
    s2 = client.post(f"{INT}/agreements/{aid}/esign/sign",
                     json={"party": "ENTERPRISE"}, headers=_mentor("刘强"))
    assert s2.status_code == 200
    s3 = client.post(f"{INT}/agreements/{aid}/esign/sign",
                     json={"party": "SCHOOL"}, headers=_mentor("刘强"))
    assert s3.status_code == 200 and s3.json()["data"]["esignStatus"] == "SIGNED"
