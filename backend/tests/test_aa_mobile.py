"""13B-P7 多端收口 · 端到端（教务学生自视图 + 教师课表）。

MB1 我的课表；MB2 我的成绩单；MB3 我的学籍+异动申请(本人)；MB4 我的毕业进度；
MB5 教师我的课表；MB6 非学生调自视图403。
"""
from __future__ import annotations

TID = 1000000000000000001
AA = "/api/v1/academic-affairs"
MB = "/api/v1/mobile"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2301", grade="2023", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AAM01", real_name="移动甲", class_id=a.id, grade="2023",
                       major_id=1, current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"class": a.id, "student": s.id}
    db.commit()
    db.close()
    return ids


def _published_schedule(client, admin, class_id, teacher_key="counselor01"):
    bid = client.post(f"{AA}/schedule-batches", headers=admin, json={"termId": "1"}).json()["data"]["batchId"]
    client.post(f"{AA}/schedule-batches/{bid}/items", headers=admin, json={
        "weekday": 1, "slotNo": 1, "teacherKey": teacher_key, "teacherName": "王老师",
        "classId": str(class_id), "className": "软件2301", "classroom": "A101", "courseName": "高数"})
    client.post(f"{AA}/schedule-batches/{bid}/publish", headers=admin)
    return bid


def test_mb1_schedule_my(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _published_schedule(client, admin, ids["class"])
    r = client.get(f"{MB}/academic/schedule/my", headers=_stu_token("移动甲", "AAM01")).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 1  # 按行政班推导出本班课表


def test_mb2_transcript_my(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tid = client.post(f"{AA}/grade-tasks", headers=admin, json={
        "courseName": "高数", "termCode": "2023-1", "credit": 4, "usualRatio": 30, "finalRatio": 70,
        "adminSupplementReason": "测试管理员补录成绩任务"}).json()["data"]["gradeTaskId"]
    client.post(f"{AA}/grade-tasks/{tid}/scores", headers=admin,
                json={"studentId": str(ids["student"]), "usualScore": 85, "finalScore": 90})
    # R1 起成绩发布必须走完整审核链：提交→学院审→教务终审发布（school_admin01 在审核角色白名单内可代行）
    client.post(f"{AA}/grade-tasks/{tid}/submit", headers=admin)
    client.post(f"{AA}/grade-tasks/{tid}/college-review", headers=admin, json={"action": "APPROVE"})
    client.post(f"{AA}/grade-tasks/{tid}/publish", headers=admin)
    r = client.get(f"{MB}/academic/transcript/my", headers=_stu_token("移动甲", "AAM01")).json()
    assert any(g["courseName"] == "高数" for g in r["data"]["items"])


def test_mb3_status_and_submit_change(client, db_mode):
    ids = _seed(db_mode)
    stu = _stu_token("移动甲", "AAM01")
    st = client.get(f"{MB}/academic/status/my", headers=stu).json()["data"]
    assert st["studentStatus"] == "REGISTERED" and st["enrolled"] is True
    # 学生本人发起休学申请（唯一学生写入口）
    r = client.post(f"{MB}/academic/status-change", headers=stu,
                    json={"changeType": "SUSPEND", "reason": "身体原因申请休学一年"}).json()
    assert r["data"]["changeType"] == "SUSPEND" and r["data"]["studentId"] == str(ids["student"])


def test_mb4_graduation_progress_my(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{AA}/graduation-audit-batches", headers=admin, json={
        "batchName": "2023届", "gradeYear": "2023"}).json()["data"]["batchId"]
    client.post(f"{AA}/graduation-audit-batches/{bid}/generate", headers=admin,
                json={"studentIds": [str(ids["student"])]})
    client.post(f"{AA}/graduation-audit-batches/{bid}/precheck", headers=admin)
    r = client.get(f"{MB}/academic/graduation/my", headers=_stu_token("移动甲", "AAM01")).json()["data"]
    assert r["hasAudit"] is True
    # 毕业预审供数维度（此前断言 7 已过时——precheck `_run_items` 现无条件产出 11 项；
    # 改为校验维度键集合而非 magic number，增删维度时能精确定位差异，不再静默漂移）。
    assert {it["item"] for it in r["items"]} == {
        "STATUS", "CREDIT", "COURSE_REQUIRED", "COURSE_ELECTIVE", "PRACTICE",
        "INTERNSHIP", "GRADUATION_DESIGN", "DISCIPLINE", "EMPLOYMENT", "ARCHIVE", "FEE"}


def test_mb5_teacher_schedule_my(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _published_schedule(client, admin, ids["class"], teacher_key="counselor01")
    r = client.get(f"{MB}/academic/teacher-schedule/my", headers=_hdr(client, "counselor01")).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 1


def test_mb6_non_student_403(client, db_mode):
    _seed(db_mode)
    r = client.get(f"{MB}/academic/schedule/my", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403
