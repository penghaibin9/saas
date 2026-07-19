"""教师工作量申报端到端（正方 教师端1.18/1.19 对标）：
教师申报(教学/监考/阅卷/出卷) → 教务台账可见 → 审核通过/驳回 → 通过计入工作量统计 declaredHours。MySQL-only。
"""
from __future__ import annotations

MB = "/api/v1/mobile"
AB = "/api/v1/academic-affairs"
MAIN = 1000000000000000001


def _teacher_token(real_name, login):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{login}", "realName": real_name, "loginName": login, "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "ACADEMIC_TEACHER", "clientType": "MP"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_teaching_task(teacher_key, hours=40):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    db = get_sessionmaker()()
    db.add(AaTeachingTask(tenant_id=MAIN, batch_id=1, course_id=1, course_name="高等数学",
                          teacher_key=teacher_key, teacher_name="王老师", total_hours=hours))
    db.commit(); db.close()


def test_workload_declare_review_and_stats(client, db_mode):
    _seed_teaching_task("wl_teacher", 40)
    hdr = _teacher_token("王老师", "wl_teacher")
    # 课时<=0 → 400
    bad = client.post(f"{MB}/teacher/academic/workload/submit", headers=hdr,
                      json={"category": "INVIGILATE", "hours": 0})
    assert bad.status_code == 400, bad.text
    # 类别非法 → 400
    bad2 = client.post(f"{MB}/teacher/academic/workload/submit", headers=hdr,
                       json={"category": "XXX", "hours": 6})
    assert bad2.status_code == 400
    # 正常申报
    ok = client.post(f"{MB}/teacher/academic/workload/submit", headers=hdr,
                     json={"category": "INVIGILATE", "hours": 6, "termCode": "2026-1", "description": "期末监考3场"})
    assert ok.status_code == 200, ok.text
    my = client.get(f"{MB}/teacher/academic/workload/my", headers=hdr).json()["data"]["items"]
    assert len(my) == 1 and my[0]["status"] == "SUBMITTED" and my[0]["categoryLabel"] == "监考"
    did = my[0]["declarationId"]
    # 教务台账可见
    admin = _admin(client)
    lst = client.get(f"{AB}/workload-declarations", headers=admin).json()["data"]
    assert any(x["declarationId"] == did for x in lst["items"])
    # 审核通过
    rv = client.post(f"{AB}/workload-declarations/{did}/review", headers=admin, json={"action": "APPROVE"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "APPROVED"
    # 计入工作量统计 declaredHours（该教师授课40 + 申报6）
    ws = client.get(f"{AB}/stats/workload", headers=admin).json()["data"]
    row = [r for r in ws["ranking"] if r["teacherKey"] == "wl_teacher"]
    assert row and row[0]["declaredHours"] == 6.0 and row[0]["combinedHours"] == 46.0


def test_workload_reject_requires_reason(client, db_mode):
    hdr = _teacher_token("李老师", "wl_teacher2")
    did = client.post(f"{MB}/teacher/academic/workload/submit", headers=hdr,
                      json={"category": "MARKING", "hours": 4}).json()["data"]["declarationId"]
    admin = _admin(client)
    # 驳回原因过短 → 400
    bad = client.post(f"{AB}/workload-declarations/{did}/review", headers=admin, json={"action": "REJECT", "note": "x"})
    assert bad.status_code == 400
    ok = client.post(f"{AB}/workload-declarations/{did}/review", headers=admin,
                     json={"action": "REJECT", "note": "重复申报，已在教学工作量中体现"})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "REJECTED"


def test_workload_teacher_only_sees_own(client, db_mode):
    a = _teacher_token("甲老师", "wl_a")
    b = _teacher_token("乙老师", "wl_b")
    client.post(f"{MB}/teacher/academic/workload/submit", headers=a, json={"category": "TEACHING", "hours": 8})
    mine_b = client.get(f"{MB}/teacher/academic/workload/my", headers=b).json()["data"]["items"]
    assert mine_b == []
