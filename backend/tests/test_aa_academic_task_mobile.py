"""教务中心 · 移动端教学任务确认（新聚合 affairs_academic_my_tasks + teacher_act 包装）。
全部经 HTTP client 走真库(db_mode)。PC 端既有 test_aa_teaching_task.py::test_tt9 已覆盖
teacher_act 本身的越权拦截（403 NO_DATA_SCOPE）；本文件专门覆盖移动端「我的任务」聚合
（list_all_tasks(mine=True) 首次经 mobile 路径覆盖）以及移动端确认/退回全链路。

夹具必须跟随正式教学任务合同：真实学院/专业/行政班、满足质量规则的培养方案、
完整并已发布的正式学期。不能再用 major_id=1、裸 term 等旧最小夹具让前置校验先失败。
"""
from __future__ import annotations

from datetime import date, timedelta

MOB = "/api/v1/mobile"
BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass

    db = get_sessionmaker()()
    seq = db.query(College).filter(College.tenant_id == TID).count() + 1
    college = College(
        tenant_id=TID,
        college_name=f"移动教学任务学院{seq}",
        status="ACTIVE",
    )
    db.add(college); db.flush()
    major = Major(
        tenant_id=TID,
        college_id=college.id,
        major_name=f"移动教学任务软件技术{seq}",
        status="ACTIVE",
    )
    db.add(major); db.flush()
    klass = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"软件270{seq}",
        grade="2027",
        status="ACTIVE",
    )
    db.add(klass); db.flush()
    ids = {"college": int(college.id), "major": int(major.id), "class": int(klass.id)}
    db.commit(); db.close()
    return ids


def _enabled_course(client, hdr, code):
    created = client.post(f"{BASE}/courses", headers=hdr, json={
        "courseCode": code, "courseName": "程序设计", "category": "MAJOR_CORE", "nature": "REQUIRED",
        "credit": 4, "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16,
        "examMode": "EXAM"})
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["courseId"]
    submitted = client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    assert submitted.status_code == 200, submitted.text
    college = client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    assert college.status_code == 200, college.text
    academic = client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    assert academic.status_code == 200, academic.text
    return cid


def _published_bound_program(client, hdr, course_id, class_id, major_id):
    created = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": f"软件技术2027方案-{course_id}",
        "majorId": str(major_id),
        "gradeYear": "2027",
        "totalCredits": 4,
    })
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["programId"]
    added = client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(course_id), "courseName": "程序设计", "openTermNo": 1,
        "module": "专业核心", "credit": 4})
    assert added.status_code == 200, added.text

    from tests.support_program_quality_fixture import seed_program_quality_requirements
    seed_program_quality_requirements(pid, total_credits=4)

    submitted = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert submitted.status_code == 200, submitted.text
    college = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert college.status_code == 200, college.text
    academic = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert academic.status_code == 200, academic.text
    bound = client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={
        "gradeYear": "2027", "classId": str(class_id)})
    assert bound.status_code == 200, bound.text
    return pid


def _term(client, hdr, year="2031-2032"):
    start_year = int(year[:4])
    start = date(start_year, 9, 1)
    created = client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": year,
        "termNo": 1,
        "termName": f"{year}第1学期",
        "startDate": start.isoformat(),
        "endDate": (start + timedelta(days=140)).isoformat(),
        "teachingWeeks": 18,
    })
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["termId"]
    published = client.post(f"{BASE}/terms/{tid}/publish", headers=hdr)
    assert published.status_code == 200, published.text
    return tid


def _assigned_task(client, hdr, code, class_id, major_id,
                   teacher_key="academic01", teacher_name="赵敏"):
    """正式建课→方案→学期→生成批次→分配给指定教师，返回 taskId。"""
    cid = _enabled_course(client, hdr, code)
    _published_bound_program(client, hdr, cid, class_id, major_id)
    digits = "".join(ch for ch in code if ch.isdigit())
    offset = int(digits[-1]) if digits else 1
    start_year = 2030 + offset
    tid = _term(client, hdr, year=f"{start_year}-{start_year + 1}")
    generated = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                            json={"termId": str(tid)})
    assert generated.status_code == 200, generated.text
    bid = generated.json()["data"]["batchId"]
    listed = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr)
    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]["items"]
    assert items, listed.text
    task_id = items[0]["taskId"]
    assigned = client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr,
                           json={"teacherName": teacher_name, "teacherKey": teacher_key})
    assert assigned.status_code == 200, assigned.text
    return task_id


def test_my_tasks_scope_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _assigned_task(client, hdr, "MT101", ids["class"], ids["major"])

    mine = client.get(f"{MOB}/teacher/academic/tasks", headers=_hdr(client, "academic01")).json()
    assert mine["code"] == 0
    assert any(t["taskId"] == task_id for t in mine["data"]["list"])

    other = client.get(f"{MOB}/teacher/academic/tasks", headers=_hdr(client, "teacher01")).json()
    assert other["code"] == 0
    assert not any(t["taskId"] == task_id for t in other["data"]["list"])


def test_confirm_flow_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _assigned_task(client, hdr, "MT102", ids["class"], ids["major"])
    self_hdr = _hdr(client, "academic01")

    ok = client.post(f"{MOB}/teacher/academic/tasks/{task_id}/act", headers=self_hdr,
                     json={"action": "CONFIRM"})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "TEACHER_CONFIRMED"

    mine = client.get(f"{MOB}/teacher/academic/tasks", headers=self_hdr).json()["data"]["list"]
    row = next(t for t in mine if t["taskId"] == task_id)
    assert row["status"] == "TEACHER_CONFIRMED"


def test_reject_reason_validation_and_flow_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _assigned_task(client, hdr, "MT103", ids["class"], ids["major"])
    self_hdr = _hdr(client, "academic01")

    bad = client.post(f"{MOB}/teacher/academic/tasks/{task_id}/act", headers=self_hdr,
                      json={"action": "REJECT", "reason": "太短"})
    assert bad.status_code == 400

    ok = client.post(f"{MOB}/teacher/academic/tasks/{task_id}/act", headers=self_hdr,
                     json={"action": "REJECT", "reason": "课表冲突，无法承担该教学任务"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "REJECTED_BY_TEACHER"
    assert ok.json()["data"]["rejectReason"] == "课表冲突，无法承担该教学任务"


def test_cross_teacher_act_403_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _assigned_task(client, hdr, "MT104", ids["class"], ids["major"])
    other_hdr = _hdr(client, "teacher01")

    r = client.post(f"{MOB}/teacher/academic/tasks/{task_id}/act", headers=other_hdr,
                    json={"action": "CONFIRM"})
    assert r.status_code == 403
