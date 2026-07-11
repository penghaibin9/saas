"""多角色岗位实习验收脚本（模拟 PC/小程序各角色点击后的 API 链路）。"""
from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from app.main import app

TID = 1000000000000000001
INT = "/api/v1/internship"
MOB = "/api/v1/mobile"
client = TestClient(app)


def _admin():
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _mentor(name="刘强"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(TID), "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student(sno="ROLE-STU-01"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-role-stu", "realName": "角色测试生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def seed():
    import uuid
    from app.db.session import get_sessionmaker
    from app.models import InternshipAgreement, InternshipBatch, InternshipRecord, StudentProfile
    suffix = uuid.uuid4().hex[:8]
    db = get_sessionmaker()()
    try:
        b = InternshipBatch(tenant_id=TID, batch_name="角色验收批次", batch_no=f"ROLE-BATCH-{suffix}",
                            status="RUNNING", planned_count=5)
        db.add(b)
        db.flush()
        sno = f"ROLE-STU-{suffix[:6]}"
        s = StudentProfile(tenant_id=TID, student_no=sno, real_name="角色测试生",
                           current_stage="INTERNSHIP", status="ACTIVE")
        db.add(s)
        db.flush()
        r = InternshipRecord(tenant_id=TID, student_id=s.id, batch_id=b.id, advisor_name="刘强",
                             enterprise_name="验收企业", position_name="验收岗", status="ONBOARD")
        db.add(r)
        db.flush()
        a = InternshipAgreement(tenant_id=TID, internship_id=r.id, student_id=s.id,
                                status="PENDING_STUDENT", rendered_body="角色验收协议正文")
        db.add(a)
        db.flush()
        db.commit()
        return b.id, r.id, sno, a.id
    finally:
        db.close()


def check(name, resp):
    ok = resp.status_code == 200 and resp.json().get("code") == 0
    print(f"{'[OK]' if ok else '[FAIL]'} {name}: {resp.status_code} {resp.json().get('message', '')[:40]}")
    if not ok:
        print("  ", resp.json())
        sys.exit(1)


def main():
    batch_id, _, sno, aid = seed()
    admin, mentor, stu = _admin(), _mentor(), _student(sno)
    # 管理员：实习计划书
    check("管理员-保存计划", client.put(f"{INT}/plans/batch/{batch_id}",
        json={"title": "角色验收计划", "content": "角色验收计划正文" * 5,
              "tasks": [
                  {"name": "完成岗前培训", "requirement": "上传培训证明", "deadline": "2026-12-31T23:59:00"},
                  {"name": "提交首周总结", "requirement": "不少于300字"}
              ]},
        headers=admin))
    check("管理员-发布计划", client.post(f"{INT}/plans/batch/{batch_id}/publish", headers=admin))
    check("管理员-计划确认台账", client.get(f"{INT}/plan-acks", headers=admin))
    # 学生：小程序计划确认 + 保险提交
    check("学生-查看计划", client.get(f"{MOB}/internship/plan", headers=stu))
    check("学生-确认计划", client.post(f"{MOB}/internship/plan/acknowledge", headers=stu))
    check("学生-提交任务1", client.post(f"{MOB}/internship/plan/tasks/1/submit",
        json={"studentNote": "已完成岗前培训并提交证明材料"}, headers=stu))
    check("学生-提交保险", client.post(f"{MOB}/internship/insurance",
        json={"policyNo": "R-001", "insurerName": "验收保险"}, headers=stu))
    # 导师：保险核验 + 过程报告/变更列表
    ins = client.get(f"{INT}/insurances", params={"status": "PENDING_VERIFY"}, headers=mentor).json()
    iid = ins["data"]["items"][0]["id"]
    check("导师-保险核验", client.post(f"{INT}/insurances/{iid}/verify",
        json={"action": "APPROVE", "comment": "通过"}, headers=mentor))
    check("导师-变更列表", client.get(f"{INT}/change-requests", headers=mentor))
    check("导师-过程报告", client.get(f"{INT}/process-reports", headers=mentor))
    check("导师-看板", client.get(f"{INT}/dashboard", headers=mentor))
    # 三方协议电子签（INTERNAL）
    check("导师-发起电子签", client.post(f"{INT}/agreements/{aid}/esign/start", headers=mentor))
    check("学生-电子签", client.post(f"{MOB}/internship/agreements/{aid}/esign/sign", headers=stu))
    check("导师-企业电子签", client.post(f"{INT}/agreements/{aid}/esign/sign",
        json={"party": "ENTERPRISE"}, headers=mentor))
    check("导师-学校电子签", client.post(f"{INT}/agreements/{aid}/esign/sign",
        json={"party": "SCHOOL"}, headers=mentor))
    check("导师-协议列表", client.get(f"{INT}/agreements", headers=mentor))
    # 任务完成度：导师批阅
    prog = client.get(f"{INT}/plan-task-progress", params={"status": "SUBMITTED", "batchId": str(batch_id)},
                      headers=mentor).json()
    if prog.get("code") == 0 and prog.get("data", {}).get("items"):
        pid = prog["data"]["items"][0]["id"]
        check("导师-任务完成确认", client.post(f"{INT}/plan-task-progress/{pid}/review",
            json={"action": "APPROVE", "comment": "通过"}, headers=mentor))
    check("导师-任务完成汇总", client.get(f"{INT}/plans/batch/{batch_id}/task-summary", headers=mentor))
    print("\n多角色验收全部通过。")


if __name__ == "__main__":
    main()
