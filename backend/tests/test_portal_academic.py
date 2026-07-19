"""学生 PC 门户 · 教务学业（第3期）测试（MySQL 真库 via db_mode）：

我的成绩单查看(本人) / 成绩单打印留痕(水印) / 非学生拒绝。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/academic"
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
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="F", grade="2022",
                          current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def test_transcript_view(client, db_mode):
    _seed("AC-001", "教务一")
    h = _stu_token("教务一", "AC-001")
    r = client.get(f"{PORTAL}/transcript", headers=h).json()
    assert r["code"] == 0  # 无成绩也返回空成绩单结构


def test_transcript_print(client, db_mode):
    _seed("AC-002", "教务二")
    h = _stu_token("教务二", "AC-002")
    r = client.post(f"{PORTAL}/transcript/print", headers=h, json={"bizId": "T1"}).json()
    assert r["code"] == 0 and r["data"]["watermark"] == "教务二"


def test_schedule_and_selection_views(client, db_mode):
    _seed("AC-010", "教务十")
    h = _stu_token("教务十", "AC-010")
    assert client.get(f"{PORTAL}/schedule", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/course-selection", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/course-selection/records", headers=h).json()["code"] == 0


def test_enroll_requires_course_id(client, db_mode):
    _seed("AC-011", "教务十一")
    h = _stu_token("教务十一", "AC-011")
    # 缺 selectionCourseId → 校验失败
    assert client.post(f"{PORTAL}/course-selection/enroll", headers=h, json={}).json()["code"] != 0
    assert client.post(f"{PORTAL}/course-selection/drop", headers=h, json={}).json()["code"] != 0


def test_status_view_and_change_guards(client, db_mode):
    _seed("AC-020", "教务廿")
    h = _stu_token("教务廿", "AC-020")
    assert client.get(f"{PORTAL}/status", headers=h).json()["code"] == 0
    # 缺 changeType / 事由过短 → 校验失败
    assert client.post(f"{PORTAL}/status-change", headers=h,
                       json={"reason": "家庭原因需转专业"}).json()["code"] != 0
    assert client.post(f"{PORTAL}/status-change", headers=h,
                       json={"changeType": "TRANSFER_MAJOR", "reason": "短"}).json()["code"] != 0
    # 打印审批表
    p = client.post(f"{PORTAL}/status-change/print", headers=h, json={"bizId": "SC1"}).json()
    assert p["code"] == 0 and p["data"]["watermark"] == "教务廿"


def test_exam_makeup_audit_views(client, db_mode):
    _seed("AC-030", "教务卅")
    h = _stu_token("教务卅", "AC-030")
    assert client.get(f"{PORTAL}/exam", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/exam/defer", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/makeup", headers=h).json()["code"] == 0
    audit = client.get(f"{PORTAL}/graduation-audit", headers=h).json()
    assert audit["code"] == 0
    d = audit["data"]
    assert "progress" in d and "credits" in d and "warnings" in d


def test_retake_requires_course(client, db_mode):
    _seed("AC-031", "教务卅一")
    h = _stu_token("教务卅一", "AC-031")
    assert client.post(f"{PORTAL}/retake/apply", headers=h, json={}).json()["code"] != 0


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/transcript", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/transcript/print", headers=admin, json={}).json()["code"] == 403001
    assert client.get(f"{PORTAL}/schedule", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/course-selection", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/course-selection/enroll", headers=admin,
                       json={"selectionCourseId": "1"}).json()["code"] == 403001
    assert client.get(f"{PORTAL}/status", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/status-change", headers=admin,
                       json={"changeType": "TRANSFER_MAJOR", "reason": "家庭原因需转专业"}).json()["code"] == 403001
    assert client.get(f"{PORTAL}/makeup", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/graduation-audit", headers=admin).json()["code"] == 403001
