"""毕业设计中心 · 移动端教师成果审核 + 附件真实预览/下载测试：
- 学生带真实附件(file_id)提交开题/成果 → 教师详情解析出可下载附件（文件中心 t_file_object）→ 真实下载 200；
- 教师成果批阅 APPROVE/REJECT，查重超标 GD-R09 不可直接通过；SCOPED 越权 403、不存在 404。
全部走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
MOBILE = "/api/v1/mobile"
FILES = "/api/v1/files"
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


def _gd_student_with_topic(client, h, no, name, advisor="成果张老师"):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": advisor,
        "capacity": 1, "submitReview": True}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent, GraduationTaskBook
    db = get_sessionmaker()()
    stu = db.get(GraduationStudent, int(gid))
    stu.stage = "FINAL_CHECK"
    db.add(GraduationTaskBook(
        tenant_id=stu.tenant_id, gd_student_id=stu.id, taskbook_version=1,
        status="CONFIRMED", objective="目标", content="内容", history_json=[],
    ))
    db.add(GraduationMidterm(
        tenant_id=stu.tenant_id, gd_student_id=stu.id,
        status="CHECKED_PASS", conclusion="PASS",
        check_comment="中期通过", checked_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()
    return gid


def _upload(client, headers):
    r = client.post(f"{FILES}/upload", headers=headers,
                    files={"file": ("thesis.pdf", b"%PDF-1.4 real bytes for graduation attachment", "application/pdf")})
    return r.json()["data"]["fileId"]


def test_final_review_and_real_attachments(client, auth_headers, db_mode):
    h = auth_headers
    name = "成果详情生"
    _gd_student_with_topic(client, h, "FN001", name)
    sh = _stu_token(name)

    # 学生带真实附件提交开题 → 教师开题详情能解析出可下载附件
    fid1 = _upload(client, sh)
    client.post(f"{MOBILE}/graduation/proposal", headers=sh, json={
        "background": "背景真实内容", "plan": "方案真实内容", "outcome": "成果真实内容",
        "attachments": [fid1]})
    pid = client.get(f"{MOBILE}/graduation/proposal", headers=sh).json()["data"]["latest"]["id"]
    pdetail = client.get(f"{MOBILE}/teacher/graduation/proposal/{pid}", headers=h).json()["data"]
    assert len(pdetail["attachmentsList"]) == 1
    att = pdetail["attachmentsList"][0]
    assert att["fileId"] == str(fid1)
    assert att["fileName"] == "thesis.pdf"
    assert att["downloadUrl"] == f"/api/v1/graduation/materials/{fid1}/download"
    # 真实下载走鉴权+审计接口，返回 200
    dl = client.get(att["downloadUrl"], headers=h)
    assert dl.status_code == 200
    assert client.get(f"/api/v1/files/download/{fid1}", headers=h).status_code == 404

    # 学生带附件提交成果初稿（无查重率）
    fid2 = _upload(client, sh)
    client.post(f"{MOBILE}/graduation/final", headers=sh,
                json={"finalType": "初稿", "attachments": [fid2]})
    students = client.get(f"{MOBILE}/teacher/graduation", headers=h).json()["data"]
    finals = students.get("finalDetail") or []
    assert any(f["studentName"] == name for f in finals)
    myfinal = next(f for f in finals if f["studentName"] == name)
    fdid = myfinal["id"]

    # 教师成果详情：真实类型/版本 + 解析出的附件
    fdetail = client.get(f"{MOBILE}/teacher/graduation/final/{fdid}", headers=h).json()["data"]
    assert fdetail["type"] == "初稿"
    assert fdetail["studentName"] == name
    assert len(fdetail["attachmentsList"]) == 1
    assert fdetail["attachmentsList"][0]["fileId"] == str(fid2)

    # SCOPED 非本人指导教师 → 403
    outsider = client.get(f"{MOBILE}/teacher/graduation/final/{fdid}", headers=_teacher_token("成果范围外老师"))
    assert outsider.json()["code"] != 0
    # 不存在 → 404
    assert client.get(f"{MOBILE}/teacher/graduation/final/999999", headers=h).json()["code"] != 0

    # 教师批阅通过（无查重超标）
    ok = client.post(f"{MOBILE}/teacher/graduation/final/{fdid}/review", headers=h,
                     json={"action": "APPROVE"})
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["status"] == "APPROVED"


def test_final_review_reject_needs_reason(client, auth_headers, db_mode):
    h = auth_headers
    name = "成果退回生"
    _gd_student_with_topic(client, h, "FN002", name, advisor="成果李老师")
    sh = _stu_token(name)
    client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "初稿"})
    finals = client.get(f"{MOBILE}/teacher/graduation", headers=h).json()["data"]["finalDetail"]
    fdid = next(f["id"] for f in finals if f["studentName"] == name)
    # 退回不填原因 → 校验失败
    bad = client.post(f"{MOBILE}/teacher/graduation/final/{fdid}/review", headers=h,
                      json={"action": "REJECT", "comment": "短"})
    assert bad.json()["code"] != 0
    # 退回填足原因 → 成功，状态 REJECTED
    ok = client.post(f"{MOBILE}/teacher/graduation/final/{fdid}/review", headers=h,
                     json={"action": "REJECT", "comment": "论文结构不完整，请补充实验章节后重交"})
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["status"] == "REJECTED"
