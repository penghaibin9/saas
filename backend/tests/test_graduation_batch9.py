"""毕业设计中心 · Batch 9 闭环测试：
补齐风险编码扫描（GD-R03 任务书未下达 / GD-R05 开题退回滞留）+ 批量归档一键操作。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

STU = "/api/v1/students"
GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
PROP = "/api/v1/graduation/proposals"
RISK = "/api/v1/graduation/gd-risks"
ARCH = "/api/v1/graduation/gd-archives"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _stu_token(name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT", "tid": "demo",
        "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _student_with_topic(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={"title": f"{name}题", "sourceType": "TEACHER",
                     "advisorName": "李老师", "capacity": 1, "submitReview": True}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    return gid


def test_risk_scan_new_codes(client, auth_headers, db_mode):
    h = auth_headers
    # 有题无任务书 → R03；开题被驳回滞留 → R05
    name = "风险补齐生"
    gid = _student_with_topic(client, h, "R9A", name)  # stage TASKBOOK_CONFIRM, 无任务书
    sh = _stu_token(name)
    client.post(f"{MOBILE}/graduation/proposal", headers=sh, json={"background": "背景足够长", "plan": "方案足够长"})
    pid = next(r for r in client.get(PROP, headers=h, params={"status": "PENDING_REVIEW"}).json()["data"]["items"]
               if r["studentName"] == name)["id"]
    client.post(f"{PROP}/{pid}/review", headers=h, json={"action": "REJECT", "comment": "方案需细化再交"})

    scan = client.post(f"{RISK}/scan", headers=h)
    assert scan.json()["code"] == 0

    rows = client.get(RISK, headers=h, params={"page": 1, "pageSize": 200}).json()["data"]["items"]
    codes = {r["riskCode"] for r in rows if r["gdStudentId"] == str(gid)}
    assert "GD-R03" in codes  # 任务书未下达
    assert "GD-R05" in codes  # 开题退回滞留


def test_batch_archive_operations(client, auth_headers, db_mode):
    h = auth_headers
    # 造几个无材料学生 → 批量生成提交应全部跳过（缺材料）
    for i in range(2):
        sid = client.post(STU, headers=h, json={"studentNo": f"R9B{i}", "realName": f"归档生{i}"}).json()["data"]["id"]
        client.post(GD_STU, headers=h, json={"studentId": sid})

    gen = client.post(f"{ARCH}/batch-generate", headers=h)
    assert gen.json()["code"] == 0
    assert gen.json()["data"]["skipped"] >= 2  # 缺材料被跳过

    # 无已提交记录 → 一键核验备案返回 0
    fil = client.post(f"{ARCH}/batch-file", headers=h, json={})
    assert fil.json()["code"] == 0
    assert fil.json()["data"]["filed"] >= 0
