"""教务中心 · 移动端教学任务确认（新聚合 affairs_academic_my_tasks + teacher_act 包装）。
全部经 HTTP client 走真库(db_mode)。PC 端既有 test_aa_teaching_task.py::test_tt9 已覆盖
teacher_act 本身的越权拦截（403 NO_DATA_SCOPE）；本文件专门覆盖移动端「我的任务」聚合
（list_all_tasks(mine=True) 首次经 mobile 路径覆盖）以及移动端确认/退回全链路。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=1000000000000000001, major_id=1, class_name="软件2701",
                    grade="2027", status="ACTIVE")
    db.add(a); db.flush()
    ids = {"class": a.id}
    db.commit()
    db.close()
    return ids


def _enabled_course(client, hdr, code):
    cid = client.post(f"{BASE}/courses", headers=hdr, json={
        "courseCode": code, "courseName": "程序设计", "category": "MAJOR_CORE", "nature": "REQUIRED",
        "credit": 4, "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16,
        "examMode": "EXAM"}).json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    return cid


def _published_bound_program(client, hdr, course_id, class_id):
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "软件技术2027方案", "majorId": "1", "gradeYear": "2027",
        "totalCredits": 4}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(course_id), "courseName": "程序设计", "openTermNo": 1,
        "module": "专业核心", "credit": 4})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={
        "gradeYear": "2027", "classId": str(class_id)})
    return pid


def _term(client, hdr, year="2027-2028"):
    return client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": year, "termNo": 1}).json()["data"]["termId"]


def _assigned_task(client, hdr, code, class_id, teacher_key="academic01", teacher_name="赵敏"):
    """建课→方案→学期→生成批次→分配给指定教师，返回 taskId。"""
    cid = _enabled_course(client, hdr, code)
    _published_bound_program(client, hdr, cid, class_id)
    tid = _term(client, hdr, year=f"2027-{code}")
    bid = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                      json={"termId": str(tid)}).json()["data"]["batchId"]
    task_id = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks",
                         headers=hdr).json()["data"]["items"][0]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr,
               json={"teacherName": teacher_name, "teacherKey": teacher_key})
    return task_id


def test_my_tasks_scope_via_mobile(client, db_mode):
    """「我的任务」聚合按本人 teacherKey 收敛：academic01 可见自己被分配的任务，
    无关教师 teacher01 看不到（mine=True 过滤此前完全没有测试经由 mobile 路径覆盖）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _assigned_task(client, hdr, "MT101", ids["class"])

    mine = client.get(f"{MOB}/teacher/academic/tasks", headers=_hdr(client, "academic01")).json()
    assert mine["code"] == 0
    assert any(t["taskId"] == task_id for t in mine["data"]["list"])

    other = client.get(f"{MOB}/teacher/academic/tasks", headers=_hdr(client, "teacher01")).json()
    assert other["code"] == 0
    assert not any(t["taskId"] == task_id for t in other["data"]["list"])


def test_confirm_flow_via_mobile(client, db_mode):
    """移动端确认：ASSIGNED→TEACHER_CONFIRMED，且确认后仍在「我的任务」列表内可见新状态。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _assigned_task(client, hdr, "MT102", ids["class"])
    self_hdr = _hdr(client, "academic01")

    ok = client.post(f"{MOB}/teacher/academic/tasks/{task_id}/act", headers=self_hdr,
                     json={"action": "CONFIRM"})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "TEACHER_CONFIRMED"

    mine = client.get(f"{MOB}/teacher/academic/tasks", headers=self_hdr).json()["data"]["list"]
    row = next(t for t in mine if t["taskId"] == task_id)
    assert row["status"] == "TEACHER_CONFIRMED"


def test_reject_reason_validation_and_flow_via_mobile(client, db_mode):
    """退回原因 <5 字 400；≥5 字成功退回并回填 rejectReason（同 PC teacher_act 口径）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _assigned_task(client, hdr, "MT103", ids["class"])
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
    """越权：无关教师对他人任务发起确认/退回 → 403（复用 PC teacher_act 内部 _check_teacher_scope）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _assigned_task(client, hdr, "MT104", ids["class"])
    other_hdr = _hdr(client, "teacher01")

    r = client.post(f"{MOB}/teacher/academic/tasks/{task_id}/act", headers=other_hdr,
                    json={"action": "CONFIRM"})
    assert r.status_code == 403
