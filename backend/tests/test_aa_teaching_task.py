"""13B-P3 培养方案发布 + 教学任务全链 · 端到端。

TT1 全链：建课ENABLED→方案→提交(学分校验)→两审→发布→绑年级→生成任务→分配教师→教师确认→批次提交APPROVED；
TT2 生成幂等；TT3 学分不达标禁提交方案；TT4 批次含未分配任务禁提交。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    ids = {"class": a.id}
    db.commit()
    db.close()
    return ids


def _enabled_course(client, hdr, code="TT101", credit=4):
    cid = client.post(f"{BASE}/courses", headers=hdr, json={
        "courseCode": code, "courseName": "程序设计", "category": "MAJOR_CORE", "nature": "REQUIRED",
        "credit": credit, "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16,
        "examMode": "EXAM"}).json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    return cid


def _published_bound_program(client, hdr, course_id, class_id, total=4):
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "软件技术2026方案", "majorId": "1", "gradeYear": "2026",
        "totalCredits": total}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(course_id), "courseName": "程序设计", "openTermNo": 1,
        "module": "专业核心", "credit": 4})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})  # PUBLISHED
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={
        "gradeYear": "2026", "classId": str(class_id)})  # ENABLED + ACTIVE binding
    return pid


def _term(client, hdr):
    return client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": "2026-2027", "termNo": 1}).json()["data"]["termId"]


def test_tt1_full_chain(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr)
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    g = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    assert g["data"]["tasksGenerated"] == 1
    bid = g["data"]["batchId"]
    tasks = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr).json()["data"]["items"]
    task_id = tasks[0]["taskId"]
    assert tasks[0]["weeklyHours"]  # 周学时已算(64/18)
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr,
                json={"teacherName": "王老师", "expectedStudents": 40})
    r = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=hdr,
                    json={"action": "CONFIRM"}).json()
    assert r["data"]["status"] == "TEACHER_CONFIRMED"
    b = client.post(f"{BASE}/teaching-task-batches/{bid}/submit", headers=hdr).json()
    assert b["data"]["status"] == "APPROVED"


def test_tt2_generate_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr)
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    g1 = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    assert g1["data"]["tasksGenerated"] == 1
    g2 = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    assert g2["data"]["tasksGenerated"] == 0  # 幂等，不重复生成


def test_tt3_program_credit_shortfall_blocks_submit(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT301")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "学分不足方案", "majorId": "1", "totalCredits": 120}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(cid), "courseName": "程序设计", "credit": 4})  # 仅4学分 << 120
    assert client.post(f"{BASE}/programs/{pid}/submit", headers=hdr).status_code == 400


def test_tt4_batch_submit_with_unassigned_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT401")
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    bid = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                      json={"termId": str(tid)}).json()["data"]["batchId"]
    # 未分配任何教师就提交 → 409
    assert client.post(f"{BASE}/teaching-task-batches/{bid}/submit", headers=hdr).status_code == 409
