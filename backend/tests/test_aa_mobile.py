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
    from app.models import College, Major, SchoolClass, StudentProfile
    from tests.support_grade_review_identity import seed_grade_review_identity

    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name="移动端教务回归学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="移动端教务回归专业", status="ACTIVE")
    db.add(major); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2301", grade="2023", status="ACTIVE")
    db.add(a); db.flush()
    seed_grade_review_identity(db, college_ids=[college.id])
    s = StudentProfile(
        tenant_id=TID, student_no="AAM01", real_name="移动甲",
        college_id=college.id, major_id=major.id, class_id=a.id, grade="2023",
        current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"college": college.id, "major": major.id, "class": a.id, "student": s.id}
    db.commit()
    db.close()
    return ids


def _ensure_term():
    """移动端测试使用可排课的正式学期：稳定 termId + 教学周 + 正式节次。"""
    from datetime import datetime

    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTimeSlot

    db = get_sessionmaker()()
    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == TID,
        AaTerm.year_code == "2023-2024",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        term = AaTerm(
            tenant_id=TID,
            year_code="2023-2024",
            term_no=1,
            term_name="2023-2024第1学期",
            start_date=datetime(2023, 9, 1),
            end_date=datetime(2024, 1, 31),
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=True,
        )
        db.add(term)
        db.flush()
    else:
        term.start_date = datetime(2023, 9, 1)
        term.end_date = datetime(2024, 1, 31)
        term.teaching_weeks = 18
        term.status = "PUBLISHED"
        term.is_current = True

    slot_times = {
        1: ("08:00", "08:45"), 2: ("08:55", "09:40"),
        3: ("10:00", "10:45"), 4: ("10:55", "11:40"),
        5: ("14:00", "14:45"), 6: ("14:55", "15:40"),
        7: ("16:00", "16:45"), 8: ("16:55", "17:40"),
    }
    for slot_no, (start, end) in slot_times.items():
        slot = db.query(AaTimeSlot).filter(
            AaTimeSlot.tenant_id == TID,
            AaTimeSlot.slot_no == slot_no,
            AaTimeSlot.is_deleted.is_(False),
        ).first()
        if not slot:
            db.add(AaTimeSlot(
                tenant_id=TID, slot_no=slot_no, slot_name=f"第{slot_no}节",
                start_time=start, end_time=end, enabled=True, status="ENABLED",
            ))
        else:
            slot.enabled = True
            slot.status = "ENABLED"
            slot.start_time = start
            slot.end_time = end

    term_id = int(term.id)
    db.commit()
    db.close()
    return term_id


def _seed_ready_task(term_id, class_id, teacher_key):
    """排课/成绩主链都回链同学期 READY 教学任务；不依赖共享 MySQL 残留。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, College

    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name="移动端课表回归学院", status="ACTIVE")
    db.add(college); db.flush()
    course = AaCourse(
        tenant_id=TID, course_code="MS101", course_name="高数", credit=4,
        nature="REQUIRED", status="ENABLED")
    db.add(course); db.flush()
    batch = AaTeachingTaskBatch(
        tenant_id=TID, term_id=int(term_id), batch_name="移动端课表回归教学任务批次",
        college_id=college.id, status="APPROVED")
    db.add(batch); db.flush()
    task = AaTeachingTask(
        tenant_id=TID, batch_id=batch.id, course_id=course.id, course_code="MS101", course_name="高数",
        class_id=int(class_id), teaching_class_name="软件2301",
        teacher_key=teacher_key, teacher_name="王老师", status="READY",
        weekly_hours=1, total_hours=18, start_week=1, end_week=18,
    )
    db.add(task); db.flush()
    task_id = int(task.id)
    db.commit()
    db.close()
    return task_id


def _published_schedule(client, admin, class_id, teacher_key="counselor01"):
    term_id = _ensure_term()
    task_id = _seed_ready_task(term_id, class_id, teacher_key)
    created = client.post(f"{AA}/schedule-batches", headers=admin, json={"termId": str(term_id)})
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]
    item = client.post(f"{AA}/schedule-batches/{bid}/items", headers=admin, json={
        "taskId": str(task_id),
        "weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
        "teacherKey": teacher_key, "teacherName": "王老师",
        "classId": str(class_id), "className": "软件2301", "classroom": "A101", "courseName": "高数"})
    assert item.status_code == 200, item.text
    prepublished = client.post(f"{AA}/schedule-batches/{bid}/pre-publish", headers=admin)
    assert prepublished.status_code == 200, prepublished.text
    published = client.post(f"{AA}/schedule-batches/{bid}/publish", headers=admin)
    assert published.status_code == 200, published.text
    return bid


def test_mb1_schedule_my(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _published_schedule(client, admin, ids["class"])
    r = client.get(f"{MB}/academic/schedule/my", headers=_stu_token("移动甲", "AAM01")).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 1


def test_mb2_transcript_my(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    term_id = _ensure_term()
    teaching_task_id = _seed_ready_task(term_id, ids["class"], "academic01")
    created = client.post(f"{AA}/grade-tasks", headers=admin, json={
        "teachingTaskId": str(teaching_task_id), "usualRatio": 30, "finalRatio": 70})
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["gradeTaskId"]
    score = client.post(f"{AA}/grade-tasks/{tid}/scores", headers=admin,
                        json={"studentId": str(ids["student"]), "usualScore": 85, "finalScore": 90})
    assert score.status_code == 200, score.text
    submitted = client.post(f"{AA}/grade-tasks/{tid}/submit", headers=admin)
    assert submitted.status_code == 200, submitted.text
    reviewed = client.post(f"{AA}/grade-tasks/{tid}/college-review", headers=admin, json={"action": "APPROVE"})
    assert reviewed.status_code == 200, reviewed.text
    published = client.post(f"{AA}/grade-tasks/{tid}/publish", headers=admin)
    assert published.status_code == 200, published.text
    r = client.get(f"{MB}/academic/transcript/my", headers=_stu_token("移动甲", "AAM01")).json()
    assert any(g["courseName"] == "高数" for g in r["data"]["items"])


def test_mb3_status_and_submit_change(client, db_mode):
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from tests.support_status_change_identity import seed_status_change_identity

    db = get_sessionmaker()()
    seed_status_change_identity(db, class_ids=[ids["class"]], college_ids=[ids["college"]])
    db.commit()
    db.close()

    stu = _stu_token("移动甲", "AAM01")
    st = client.get(f"{MB}/academic/status/my", headers=stu).json()["data"]
    assert st["studentStatus"] == "REGISTERED" and st["enrolled"] is True
    response = client.post(f"{MB}/academic/status-change", headers=stu,
                           json={"changeType": "SUSPEND", "reason": "身体原因申请休学一年"})
    assert response.status_code == 200, response.text
    r = response.json()
    assert r["data"]["changeType"] == "SUSPEND" and r["data"]["studentId"] == str(ids["student"])


def test_mb4_graduation_progress_my(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    created = client.post(f"{AA}/graduation-audit-batches", headers=admin, json={
        "batchName": "2023届", "gradeYear": "2023"})
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]
    generated = client.post(f"{AA}/graduation-audit-batches/{bid}/generate", headers=admin,
                            json={"studentIds": [str(ids["student"])]})
    assert generated.status_code == 200, generated.text
    precheck = client.post(f"{AA}/graduation-audit-batches/{bid}/precheck", headers=admin)
    assert precheck.status_code == 200, precheck.text
    r = client.get(f"{MB}/academic/graduation/my", headers=_stu_token("移动甲", "AAM01")).json()["data"]
    assert r["hasAudit"] is True
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