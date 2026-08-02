"""复审收口：学生端附件强制、开题 canSubmit 与 topic_id 一致、成绩申诉态。"""
from __future__ import annotations

from conftest import make_org_class

from app.core.security import create_access_token

MAIN = 1000000000000000001
MOBILE = "/api/v1/mobile"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _stu(name):
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _upload(client, headers):
    r = client.post("/api/v1/files", headers=headers,
                    files={"file": ("t.pdf", b"%PDF-1.4 x", "application/pdf")},
                    params={"bizType": "GRADUATION_MATERIAL"})
    assert r.json()["code"] == 0
    return r.json()["data"]["fileId"]


def test_final_requires_attachment(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent, GraduationTaskBook
    from datetime import datetime

    h = auth_headers
    name = "强制附件生"
    sid = client.post(STU, headers=h, json={"studentNo": "ATT-REQ-01", "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    db = get_sessionmaker()()
    stu = db.get(GraduationStudent, int(gid))
    stu.stage = "FINAL_CHECK"
    stu.topic_id = 1
    stu.topic_title = "题"
    db.add(GraduationTaskBook(tenant_id=stu.tenant_id, gd_student_id=stu.id, status="CONFIRMED",
                              objective="o", content="c", history_json=[]))
    db.add(GraduationMidterm(tenant_id=stu.tenant_id, gd_student_id=stu.id,
                             status="CHECKED_PASS", conclusion="PASS",
                             check_comment="ok", checked_at=datetime.utcnow()))
    db.commit()
    db.close()
    sh = _stu(name)
    empty = client.post(f"{MOBILE}/graduation/final", headers=sh,
                        json={"finalType": "初稿", "attachments": []}).json()
    assert empty["code"] != 0
    assert "附件" in (empty.get("message") or "")
    ok = client.post(f"{MOBILE}/graduation/final", headers=sh,
                     json={"finalType": "初稿", "attachments": [_upload(client, sh)]}).json()
    assert ok["code"] == 0, ok


def test_proposal_can_submit_requires_topic_id(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent, GraduationTaskBook

    h = auth_headers
    name = "开题提示生"
    sid = client.post(STU, headers=h, json={"studentNo": "PROP-TOPIC-01", "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    db = get_sessionmaker()()
    stu = db.get(GraduationStudent, int(gid))
    stu.stage = "GUIDING"  # 阶段已过选题，但无 topic_id
    stu.topic_id = None
    db.add(GraduationTaskBook(tenant_id=stu.tenant_id, gd_student_id=stu.id, status="CONFIRMED",
                              objective="o", content="c", history_json=[]))
    db.commit()
    db.close()
    sh = _stu(name)
    view = client.get(f"{MOBILE}/graduation/proposal", headers=sh).json()
    assert view["code"] == 0
    assert view["data"]["canSubmit"] is False
    assert "选题" in (view["data"].get("reason") or "")


def test_grade_exposes_appeal_pending(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationGrade, GraduationGradeAppeal, GraduationStudent

    h = auth_headers
    name = "申诉态生"
    sid = client.post(STU, headers=h, json={"studentNo": "APPEAL-01", "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    db = get_sessionmaker()()
    stu = db.get(GraduationStudent, int(gid))
    db.add(GraduationGrade(tenant_id=stu.tenant_id, gd_student_id=stu.id,
                           total_score=80, grade_level="中等", status="PUBLISHED",
                           advisor_score=80, reviewer_score=80, defense_score=80))
    db.add(GraduationGradeAppeal(tenant_id=stu.tenant_id, gd_student_id=stu.id,
                                 reason="分数计算有误请复核", status="PENDING"))
    db.commit()
    db.close()
    sh = _stu(name)
    g = client.get(f"{MOBILE}/graduation/grade", headers=sh).json()
    assert g["code"] == 0
    assert g["data"]["published"] is True
    assert g["data"]["canAppeal"] is False
    assert g["data"]["latestAppeal"]["status"] == "PENDING"
