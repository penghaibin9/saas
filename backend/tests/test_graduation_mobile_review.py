"""毕业设计中心 · 移动端教师开题详情（批阅前真实查看）测试：
- 教师能拉取开题真实内容（背景/方案/预期成果 + 历史版本 + 附件数），不再是「详见 PC 端」空壳；
- SCOPED 教师查看范围外开题 → 403；不存在的开题 → 404。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _teacher_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "GD_MENTOR", "clientType": "MP"})}


def _gd_student_with_topic(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": "详情张老师",
        "capacity": 1, "submitReview": True}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    return gid


def test_teacher_proposal_detail_real_content_and_scope(client, auth_headers, db_mode):
    h = auth_headers
    name = "开题详情生"
    _gd_student_with_topic(client, h, "PD001", name)
    sh = _stu_token(name)
    client.post(f"{MOBILE}/graduation/proposal", headers=sh, json={
        "background": "背景：面向职校实训的真实材料", "plan": "方案：需求→设计→实现→测试 12 周",
        "outcome": "成果：可运行系统与论文"})
    pid = client.get(f"{MOBILE}/graduation/proposal", headers=sh).json()["data"]["latest"]["id"]

    # 管理端教师（ADMIN_TENANT）可查看真实开题内容，不再是「详见 PC 端」空壳
    d = client.get(f"{MOBILE}/teacher/graduation/proposal/{pid}", headers=h).json()["data"]
    assert d["background"] == "背景：面向职校实训的真实材料"
    assert d["plan"].startswith("方案：")
    assert d["outcome"].startswith("成果：")
    assert d["studentName"] == name
    assert isinstance(d["versions"], list) and len(d["versions"]) >= 1
    assert d["status"] == "PENDING_REVIEW"

    # SCOPED 教师（非本人指导）查看范围外开题 → 403
    outsider = client.get(f"{MOBILE}/teacher/graduation/proposal/{pid}", headers=_teacher_token("范围外老师"))
    assert outsider.json()["code"] != 0

    # 不存在的开题 → 404
    missing = client.get(f"{MOBILE}/teacher/graduation/proposal/999999", headers=h)
    assert missing.json()["code"] != 0
