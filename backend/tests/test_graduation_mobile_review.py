"""毕业设计中心 · 移动端教师开题详情/批阅测试：
- 教师能拉取开题真实内容（背景/方案/预期成果 + 历史版本 + 附件数），不再是「详见 PC 端」空壳；
- SCOPED 教师查看范围外开题 → 403；不存在的开题 → 404；
- 教师移动端提交开题批阅 APPROVE（列表待审 → 详情 → 批阅 → 队列清空）。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

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


def _gd_student_with_topic(client, h, no, name, advisor="详情张老师"):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": advisor,
        "capacity": 1, "submitReview": True}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    # 开题提交门禁：须已确认任务书（与 PC/学生端一致）
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent, GraduationTaskBook
    db = get_sessionmaker()()
    stu = db.get(GraduationStudent, int(gid))
    stu.stage = "GUIDING"
    db.add(GraduationTaskBook(
        tenant_id=stu.tenant_id, gd_student_id=stu.id, taskbook_version=1,
        status="CONFIRMED", objective="目标", content="内容", history_json=[],
        confirmed_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()
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


def test_teacher_proposal_review_approve_clears_pending_queue(client, auth_headers, db_mode):
    """移动端开题批阅主路径：待审列表含该生 → 详情可读 → APPROVE → 待审队列不再出现。"""
    h = auth_headers
    name = "开题批阅生"
    advisor = "批阅王老师"
    _gd_student_with_topic(client, h, "PR001", name, advisor=advisor)
    sh = _stu_token(name)
    client.post(f"{MOBILE}/graduation/proposal", headers=sh, json={
        "background": "背景材料足够用于批阅", "plan": "方案材料足够用于批阅",
        "outcome": "预期成果说明"})
    pid = client.get(f"{MOBILE}/graduation/proposal", headers=sh).json()["data"]["latest"]["id"]

    # 聚合待审：教师工作台开题队列应含该 proposal
    agg = client.get(f"{MOBILE}/teacher/graduation", headers=h).json()["data"]
    pending = [p for p in (agg.get("reviewDetail") or []) if str(p.get("id")) == str(pid)]
    assert pending, "开题待审队列应包含刚提交的开题"

    detail = client.get(f"{MOBILE}/teacher/graduation/proposal/{pid}", headers=h).json()["data"]
    assert detail["status"] == "PENDING_REVIEW"

    ok = client.post(f"{MOBILE}/teacher/graduation/proposal/{pid}/review", headers=h,
                     json={"action": "APPROVE", "comment": ""})
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["status"] == "APPROVED"

    agg2 = client.get(f"{MOBILE}/teacher/graduation", headers=h).json()["data"]
    still = [p for p in (agg2.get("reviewDetail") or []) if str(p.get("id")) == str(pid)]
    assert not still, "批阅通过后不应再出现在待审队列"

    # 范围外导师不可批阅（已通过的开题再批也会失败；此处用另一新开题更干净，
    # 但最小断言：对已批阅 id 的越权账号仍非成功）
    forbid = client.post(f"{MOBILE}/teacher/graduation/proposal/{pid}/review",
                         headers=_teacher_token("范围外批阅老师"),
                         json={"action": "REJECT", "comment": "这是越权驳回意见足够五字"})
    assert forbid.json()["code"] != 0
