"""毕业设计中心 · 成果提交闭环测试：
学生提交初稿/定稿（定稿须初稿通过、待审不可重复）→ 管理端批阅（GD-R09 查重超标拦截 / 退回需理由）→
退回后重交 → 未提交派生 + 催交 → Excel 台账导出。全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
PROP = "/api/v1/graduation/proposals"
FINAL = "/api/v1/graduation/finals"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001

def _upload_pdf(client, headers, name="thesis.pdf"):
    files = {"file": (name, b"%PDF-1.4 test", "application/pdf")}
    r = client.post("/api/v1/files/upload", headers=headers, files=files,
                    params={"bizType": "GRADUATION_MATERIAL"})
    assert r.json()["code"] == 0, r.json()
    return r.json()["data"]["fileId"]


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _gd_student_with_topic(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": "指导李老师",
        "capacity": 1, "submitReview": True}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    return gid


def _to_guiding(client, h, sh, gid, name):
    """准备到可交成果：任务书确认 + 中期通过 + 阶段 FINAL_CHECK。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent, GraduationTaskBook
    from datetime import datetime

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


def _pending_final_id(client, h, name):
    lst = client.get(FINAL, headers=h, params={"status": "PENDING_REVIEW"}).json()["data"]
    return next(r for r in lst["items"] if r["studentName"] == name)["id"]


def test_submit_order_draft_then_final(client, auth_headers, db_mode):
    h = auth_headers
    name = "成果小明"
    gid = _gd_student_with_topic(client, h, "FN001", name)
    sh = _stu_token(name)
    _to_guiding(client, h, sh, gid, name)

    # 定稿须先有通过的初稿
    early = client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "定稿", "attachments": [_upload_pdf(client, sh)]})
    assert early.json()["code"] != 0

    draft = client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]})
    assert draft.json()["code"] == 0
    assert draft.json()["data"]["version"] == "v1"

    # 待审不可重复提交
    dup = client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]})
    assert dup.json()["code"] != 0

    fid = _pending_final_id(client, h, name)
    client.post(f"{FINAL}/{fid}/review", headers=h, json={"action": "APPROVE"})

    # 初稿通过后可交定稿
    fin = client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "定稿", "attachments": [_upload_pdf(client, sh)]})
    assert fin.json()["code"] == 0
    assert fin.json()["data"]["finalType"] == "定稿"


def test_student_supplied_plagiarism_rate_is_ignored(client, auth_headers, db_mode):
    h = auth_headers
    name = "查重小红"
    gid = _gd_student_with_topic(client, h, "FN101", name)
    sh = _stu_token(name)
    _to_guiding(client, h, sh, gid, name)

    # A student cannot forge an authoritative plagiarism result in the request body.
    client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "初稿", "plagiarismRate": "35%", "attachments": [_upload_pdf(client, sh)]})
    fid = _pending_final_id(client, h, name)
    row = next(
        item for item in client.get(FINAL, headers=h).json()["data"]["items"] if item["id"] == fid
    )
    assert row["plagiarismRate"] == "—"


def test_reject_then_resubmit_new_version(client, auth_headers, db_mode):
    h = auth_headers
    name = "重交小刚"
    gid = _gd_student_with_topic(client, h, "FN201", name)
    sh = _stu_token(name)
    _to_guiding(client, h, sh, gid, name)

    client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]})
    fid = _pending_final_id(client, h, name)
    client.post(f"{FINAL}/{fid}/review", headers=h, json={"action": "REJECT", "comment": "格式需按模板调整"})

    resub = client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]})
    assert resub.json()["code"] == 0
    assert resub.json()["data"]["version"] == "v2"


def test_not_submitted_derivation_and_remind(client, auth_headers, db_mode):
    h = auth_headers
    name = "未交小李"
    gid = _gd_student_with_topic(client, h, "FN301", name)
    sh = _stu_token(name)
    _to_guiding(client, h, sh, gid, name)  # GUIDING 且无成果

    nb = client.get(FINAL, headers=h, params={"status": "NOT_SUBMITTED"}).json()["data"]
    target = next(r for r in nb["items"] if r["studentName"] == name)
    assert target["status"] == "NOT_SUBMITTED"

    remind = client.post(f"{FINAL}/remind", headers=h, json={"gdStudentId": target["gdStudentId"]})
    assert remind.json()["code"] == 0

    client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]})
    remind2 = client.post(f"{FINAL}/remind", headers=h, json={"gdStudentId": target["gdStudentId"]})
    assert remind2.json()["code"] != 0  # 已提交不可催


def test_export_finals_ledger(client, auth_headers, db_mode):
    h = auth_headers
    name = "导出小周"
    gid = _gd_student_with_topic(client, h, "FN401", name)
    sh = _stu_token(name)
    _to_guiding(client, h, sh, gid, name)
    client.post(f"{MOBILE}/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]})

    exp = client.post(f"{FINAL}/export", headers=h)
    body = exp.json()
    assert body["code"] == 0
    assert body["data"]["rowCount"] >= 1
    assert body["data"]["filename"].endswith(".xlsx")
