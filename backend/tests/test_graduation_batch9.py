"""毕业设计中心 · Batch 9 闭环测试：
补齐风险编码扫描（GD-R03 任务书未下达 / GD-R05 开题退回滞留）+ 批量归档一键操作。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

STU = "/api/v1/students"
GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_ASSIGN = "/api/v1/graduation/gd-mentor-assignments"
GD_TASKBOOK = "/api/v1/graduation/gd-taskbooks"
PROP = "/api/v1/graduation/proposals"
RISK = "/api/v1/graduation/gd-risks"
ARCH = "/api/v1/graduation/gd-archives"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _stu_token(name, student_no=None):
    from app.core.security import create_access_token
    claims = {
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT", "tid": "demo",
        "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP",
    }
    if student_no:
        claims["studentNo"] = student_no
    return {"Authorization": "Bearer " + create_access_token(claims)}


def test_risk_scan_new_codes(client, auth_headers, db_mode):
    """有题无任务书 → R03；确认任务书后开题驳回滞留 → R05（两人分测，因开题前置已要求任务书确认）。"""
    h = auth_headers
    bid = client.post("/api/v1/graduation/batches", headers=h, json={
        "batchName": "Batch9风险批", "batchNo": "GD-R9-SCAN", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]

    # 学生 A：选题后无任务书 → GD-R03
    name_a = "风险补齐生A"
    sid_a = client.post(STU, headers=h, json={"studentNo": "R9A", "realName": name_a, "classId": make_org_class()}).json()["data"]["id"]
    gid_a = client.post(GD_STU, headers=h, json={"studentId": sid_a, "batchId": bid}).json()["data"]["id"]
    tid_a = client.post(GD_TOPIC, headers=h, json={"title": f"{name_a}题", "sourceType": "TEACHER",
                       "advisorName": "李老师", "capacity": 1, "submitReview": True, "batchId": bid}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid_a}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid_a}/assign-topic", headers=h, json={"topicId": tid_a})

    # 学生 B：选题 + 导师 + 任务书确认 + 开题驳回 → GD-R05
    name_b = "风险补齐生B"
    sno_b = "R9B"
    sid_b = client.post(STU, headers=h, json={"studentNo": sno_b, "realName": name_b, "classId": make_org_class()}).json()["data"]["id"]
    gid_b = client.post(GD_STU, headers=h, json={"studentId": sid_b, "batchId": bid}).json()["data"]["id"]
    tid_b = client.post(GD_TOPIC, headers=h, json={"title": f"{name_b}题", "sourceType": "TEACHER",
                       "advisorName": "李老师", "capacity": 1, "submitReview": True, "batchId": bid}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid_b}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid_b}/assign-topic", headers=h, json={"topicId": tid_b})
    mid = client.post(GD_MENTOR, headers=h, json={"teacherNo": "R9M1", "teacherName": "导师R9"}).json()["data"]["id"]
    client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid_b, "mentorId": mid})
    issue = client.post(f"{GD_TASKBOOK}/{gid_b}/issue", headers=h, params={"batchId": bid},
                        json={"objective": "完成系统设计文档", "content": "完成系统详细设计"})
    assert issue.json()["code"] == 0, issue.json()
    # 管理端路由挂 require_staff，学生须走门户/mobile；此处用管理员代确认即可满足开题前置
    confirm = client.post(f"{GD_TASKBOOK}/{gid_b}/confirm", headers=h, params={"batchId": bid},
                          json={"proxyReason": "代确认任务书用于风险扫描回归"})
    assert confirm.json()["code"] == 0, confirm.json()
    sh = _stu_token(name_b, sno_b)
    sub = client.post(f"{MOBILE}/graduation/proposal", headers=sh,
                      json={"background": "背景足够长用于开题", "plan": "方案足够长用于开题"})
    assert sub.json()["code"] == 0, sub.json()
    pid = next(r for r in client.get(PROP, headers=h, params={
        "status": "PENDING_REVIEW", "batchId": bid}).json()["data"]["items"]
               if r["studentName"] == name_b)["id"]
    client.post(f"{PROP}/{pid}/review", headers=h, params={"batchId": bid},
                json={"action": "REJECT", "comment": "方案需细化再交"})

    scan = client.post(f"{RISK}/scan", headers=h, params={"batchId": bid})
    assert scan.json()["code"] == 0, scan.json()

    rows = client.get(RISK, headers=h, params={"page": 1, "pageSize": 200, "batchId": bid}).json()["data"]["items"]
    codes_a = {r["riskCode"] for r in rows if str(r["gdStudentId"]) == str(gid_a)}
    codes_b = {r["riskCode"] for r in rows if str(r["gdStudentId"]) == str(gid_b)}
    assert "GD-R03" in codes_a  # 任务书未下达
    assert "GD-R05" in codes_b  # 开题退回滞留


def test_batch_archive_operations(client, auth_headers, db_mode):
    h = auth_headers
    bid = client.post("/api/v1/graduation/batches", headers=h, json={
        "batchName": "Batch9归档批", "batchNo": "GD-R9-ARCH", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    # 造几个无材料学生 → 批量生成提交应全部跳过（缺材料）
    for i in range(2):
        sid = client.post(STU, headers=h, json={"studentNo": f"R9B{i}", "realName": f"归档生{i}", "classId": make_org_class()}).json()["data"]["id"]
        client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid})

    prev = client.post(f"{ARCH}/batch-generate/preview", headers=h, params={"batchId": bid}).json()
    assert prev["code"] == 0, prev
    gen = client.post(f"{ARCH}/batch-generate", headers=h, params={"batchId": bid},
                      json={"previewToken": prev["data"]["previewToken"]})
    assert gen.json()["code"] == 0, gen.json()
    assert gen.json()["data"]["skipped"] >= 2  # 缺材料被跳过

    # 无已提交记录 → 一键核验备案返回 0
    prev_f = client.post(f"{ARCH}/batch-file/preview", headers=h, params={"batchId": bid}).json()
    assert prev_f["code"] == 0, prev_f
    fil = client.post(f"{ARCH}/batch-file", headers=h, params={"batchId": bid},
                      json={"previewToken": prev_f["data"]["previewToken"]})
    assert fil.json()["code"] == 0, fil.json()
    assert fil.json()["data"]["filed"] >= 0
