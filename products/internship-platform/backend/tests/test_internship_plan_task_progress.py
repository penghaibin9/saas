"""岗位实习 · 计划任务完成度跟踪。"""
from __future__ import annotations

TID = 1000000000000000001
INT = "/api/v1/internship"
MOB = "/api/v1/mobile"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _student(sno="TP-STU-01"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-tp-stu", "realName": "任务进度生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _mentor(name="刘强"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(TID), "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _seed(db_mode):
    import uuid
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile
    suffix = uuid.uuid4().hex[:6]
    db = get_sessionmaker()()
    try:
        sno = f"TP-STU-{suffix}"
        b = InternshipBatch(tenant_id=TID, batch_name="任务进度批次", batch_no=f"TP-BATCH-{suffix}",
                            status="RUNNING", planned_count=5)
        db.add(b)
        db.flush()
        s = StudentProfile(tenant_id=TID, student_no=sno, real_name="任务进度生",
                           current_stage="INTERNSHIP", status="ACTIVE")
        db.add(s)
        db.flush()
        r = InternshipRecord(tenant_id=TID, student_id=s.id, batch_id=b.id, advisor_name="刘强",
                             enterprise_name="测试企业", position_name="实习生", status="ONBOARD")
        db.add(r)
        db.flush()
        db.commit()
        return b.id, r.id, sno
    finally:
        db.close()


def test_plan_task_progress_flow(client, db_mode):
    batch_id, _, sno = _seed(db_mode)
    tasks = [
        {"sortOrder": 1, "name": "安全培训", "requirement": "完成培训"},
        {"sortOrder": 2, "name": "首周日志", "requirement": "提交日志"},
    ]
    save = client.put(f"{INT}/plans/batch/{batch_id}",
                      json={"title": "任务进度计划", "content": "正文足够长正文足够长正文足够长正文足够长", "tasks": tasks},
                      headers=_admin(client))
    pub = client.post(f"{INT}/plans/batch/{batch_id}/publish",
                      json={"expectedVersion": save.json()["data"]["version"]}, headers=_admin(client))
    assert pub.status_code == 200 and pub.json()["data"].get("taskProgressInit", 0) >= 2
    pending_acks = client.get(f"{INT}/plan-acks",
                              params={"batchId": str(batch_id), "status": "PENDING"},
                              headers=_mentor("刘强"))
    assert pending_acks.status_code == 200
    assert pending_acks.json()["data"]["total"] == 1
    assert pending_acks.json()["data"]["items"][0]["studentNo"] == sno
    stu = _student(sno)
    ack = client.post(f"{MOB}/internship/plan/acknowledge", headers=stu, json={
        "planVersion": pub.json()["data"]["version"], "expectedVersion": 0,
    })
    assert ack.status_code == 200
    acknowledged = client.get(f"{INT}/plan-acks",
                              params={"batchId": str(batch_id), "status": "ACKNOWLEDGED"},
                              headers=_mentor("刘强"))
    assert acknowledged.status_code == 200 and acknowledged.json()["data"]["total"] == 1
    sub = client.post(f"{MOB}/internship/plan/tasks/1/submit",
                      json={"studentNote": "已完成安全培训并上传证明", "expectedVersion": 0}, headers=stu)
    assert sub.status_code == 200 and sub.json()["data"]["status"] == "SUBMITTED"
    lst = client.get(f"{INT}/plan-task-progress", params={"status": "SUBMITTED", "batchId": str(batch_id)},
                     headers=_mentor("刘强"))
    assert lst.status_code == 200
    item = lst.json()["data"]["items"][0]
    pid = item["id"]
    rev = client.post(f"{INT}/plan-task-progress/{pid}/review",
                      json={"action": "APPROVE", "comment": "属实", "expectedVersion": item["version"]},
                      headers=_mentor("刘强"))
    assert rev.status_code == 200 and rev.json()["data"]["status"] == "APPROVED"
    summary = client.get(f"{INT}/plans/batch/{batch_id}/task-summary", headers=_mentor("刘强"))
    assert summary.status_code == 200 and summary.json()["data"]["avgRate"] >= 0


def test_plan_task_requires_ack(client, db_mode):
    batch_id, _, sno = _seed(db_mode)
    client.put(f"{INT}/plans/batch/{batch_id}",
               json={"title": "计划2", "content": "正文足够长正文足够长正文足够长正文足够长",
                     "tasks": [{"sortOrder": 1, "name": "任务A", "requirement": "完成"}]},
               headers=_admin(client))
    client.post(f"{INT}/plans/batch/{batch_id}/publish", headers=_admin(client))
    bad = client.post(f"{MOB}/internship/plan/tasks/1/submit",
                      json={"studentNote": "未确认就提交任务完成说明"}, headers=_student(sno))
    assert bad.status_code == 400 or bad.json().get("code") not in (0, None)
