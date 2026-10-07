"""学生 PC 门户 · 岗位实习（第5期）测试（MySQL 真库 via db_mode）：

我的实习查看 / 周报·月报校验 / 协议打印 / 成绩申诉 / 非学生拒绝。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/internship"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M", grade="2022",
                          current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def _seed_score_context(no, name):
    from datetime import datetime
    from uuid import uuid4

    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipFinalScore, InternshipRecord, StudentProfile

    db = get_sessionmaker()()
    try:
        student = StudentProfile(
            tenant_id=TID, student_no=no, real_name=name, gender="M", grade="2022",
            current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE",
        )
        db.add(student)
        db.flush()
        batch = InternshipBatch(
            tenant_id=TID, batch_name="门户成绩申诉批次",
            batch_no=f"PORTAL-APPEAL-{uuid4().hex[:8]}", status="RUNNING", planned_count=1,
        )
        db.add(batch)
        db.flush()
        record = InternshipRecord(
            tenant_id=TID, student_id=student.id, batch_id=batch.id,
            status="ASSESSING", risk_level="NONE",
        )
        db.add(record)
        db.flush()
        score = InternshipFinalScore(
            tenant_id=TID, internship_id=record.id, student_id=student.id,
            batch_id=batch.id, total_score=80, pass_line=60,
            is_pass=True, incomplete=False, status="PUBLISHED",
            published_by_name="学校管理员", published_at=datetime.utcnow(), version=1,
        )
        db.add(score)
        db.commit()
        return {"internship": record.id, "batch": batch.id, "score": score.id}
    finally:
        db.close()


def test_my_view(client, db_mode):
    _seed("IN-001", "实习一")
    h = _stu_token("实习一", "IN-001")
    assert client.get(f"{PORTAL}/my", headers=h).json()["code"] == 0


def test_weekly_and_report_guards(client, db_mode):
    _seed("IN-002", "实习二")
    h = _stu_token("实习二", "IN-002")
    # 周报缺周次 → 校验失败
    assert client.post(f"{PORTAL}/weekly/submit", headers=h,
                       json={"workContent": "x" * 20, "harvestContent": "y" * 20}).json()["code"] != 0
    # 月报缺类型 / 空内容 → 校验失败
    assert client.post(f"{PORTAL}/report/submit", headers=h,
                       json={"content": "本月实习总结长文本内容……"}).json()["code"] != 0
    assert client.post(f"{PORTAL}/report/submit", headers=h,
                       json={"reportType": "MONTHLY", "content": ""}).json()["code"] != 0


def test_agreement_print_and_score_appeal(client, db_mode):
    ids = _seed_score_context("IN-003", "实习三")
    h = _stu_token("实习三", "IN-003")
    p = client.post(f"{PORTAL}/agreement/print", headers=h, json={"bizId": "AG1"}).json()
    assert p["code"] == 0 and p["data"]["watermark"] == "实习三"
    ok = client.post(f"{PORTAL}/score/appeal", headers=h,
                     json={"internshipId": str(ids["internship"]),
                           "reason": "实习成绩与考勤/周报表现不符，申请复核。"}).json()
    assert ok["code"] == 0
    assert client.post(f"{PORTAL}/score/appeal", headers=h,
                       json={"internshipId": str(ids["internship"]), "reason": "短"}).json()["code"] != 0


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/my", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/weekly/submit", headers=admin,
                       json={"weekNo": 1, "workContent": "x" * 20, "harvestContent": "y" * 20}).json()["code"] == 403001
    assert client.post(f"{PORTAL}/agreement/print", headers=admin, json={}).json()["code"] == 403001
