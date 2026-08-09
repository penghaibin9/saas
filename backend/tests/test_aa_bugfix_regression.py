"""教务中心 Bug 修复回归：学分小数 / 期中回显 / 成绩任务去重 / 发布后成绩单一致。"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_students(n=1):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件BUG01", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    sids = []
    for i in range(n):
        s = StudentProfile(tenant_id=TID, student_no=f"BUG{i:03d}", real_name=f"修{i}", class_id=a.id,
                           current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
        db.add(s); db.flush(); sids.append(s.id)
    db.commit(); cid = a.id; db.close()
    return sids, cid


def test_bf1_program_half_credit_persists(client, db_mode):
    """培养方案总学分/课程学分快照支持 1.5、2.5、3.5，刷新后不取整。"""
    hdr = _hdr(client, "school_admin01")
    created = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "半学分方案", "gradeYear": "2026", "totalCredits": 120.5}).json()
    assert created["code"] == 0, created
    pid = created["data"]["programId"]
    assert float(created["data"]["totalCredits"]) == 120.5
    add = client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "半学分课", "credit": 1.5, "openTermNo": 1, "module": "专业核心"}).json()
    assert add["code"] == 0, add
    detail = client.get(f"{BASE}/programs/{pid}", headers=hdr).json()["data"]
    assert float(detail["totalCredits"]) == 120.5
    courses = detail.get("courses") or detail.get("courseItems") or []
    hit = next((c for c in courses if c.get("courseName") == "半学分课"), None)
    assert hit is not None
    credit = hit.get("credit") if hit.get("credit") is not None else hit.get("creditSnapshot")
    assert float(credit) == 1.5
    # 再加 2.5
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "二点五学分课", "credit": 2.5, "openTermNo": 2})
    detail2 = client.get(f"{BASE}/programs/{pid}", headers=hdr).json()["data"]
    courses2 = detail2.get("courses") or detail2.get("courseItems") or []
    assert any(float(c.get("credit") if c.get("credit") is not None else c.get("creditSnapshot")) == 2.5
               for c in courses2 if c.get("courseName") == "二点五学分课")


def test_bf2_midterm_persists_on_list_records(client, db_mode):
    """期中分保存后 GET records 必须回读 midtermScore（PC 刷新映射依赖此字段）。"""
    sids, _ = _seed_students(1)
    hdr = _hdr(client, "school_admin01")
    tid = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "期中回显课", "termCode": "2026-1", "credit": 3,
        "usualRatio": 30, "midtermRatio": 30, "finalRatio": 40,
        "adminSupplementReason": "测试管理员补录成绩任务"}).json()["data"]["gradeTaskId"]
    r = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={
        "studentId": str(sids[0]), "usualScore": 80, "midtermScore": 90, "finalScore": 70}).json()
    assert r["data"]["midtermScore"] == 90
    assert r["data"]["totalScore"] == 79  # 24+27+28
    items = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"]
    assert items[0]["midtermScore"] == 90
    assert items[0]["usualScore"] == 80
    assert items[0]["finalScore"] == 70


def test_bf3_duplicate_grade_task_same_teaching_task_409(client, db_mode):
    """同一教学任务不可产生多条有效成绩任务。"""
    hdr = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    db = get_sessionmaker()()
    tt = AaTeachingTask(tenant_id=TID, batch_id=1, course_id=1, course_name="去重课",
                        teacher_key="school_admin01", status="READY")
    db.add(tt); db.commit(); tt_id = tt.id; db.close()
    r1 = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(tt_id), "usualRatio": 30, "finalRatio": 70})
    assert r1.status_code == 200, r1.text
    r2 = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(tt_id), "usualRatio": 30, "finalRatio": 70})
    assert r2.status_code == 409, r2.text


def test_bf4_teacher_must_bind_teaching_task(client, db_mode):
    """普通教师脱离教学任务创建成绩任务必须拒绝。"""
    teacher_hdr = _hdr(client, "academic01")
    r = client.post(f"{BASE}/grade-tasks", headers=teacher_hdr, json={
        "courseName": "脱离教学任务", "usualRatio": 30, "finalRatio": 70})
    assert r.status_code in (400, 422)


def test_bf5_publish_then_transcript_consistent(client, db_mode):
    """发布后成绩单与录入总评一致；重复发布幂等冲突。"""
    sids, _ = _seed_students(1)
    hdr = _hdr(client, "school_admin01")
    tid = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "发布一致课", "termCode": "2026-BUG", "credit": 3.5,
        "usualRatio": 30, "finalRatio": 70,
        "adminSupplementReason": "测试管理员补录成绩任务"}).json()["data"]["gradeTaskId"]
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={
        "studentId": str(sids[0]), "usualScore": 80, "finalScore": 90})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    pub = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr).json()
    assert pub["data"]["status"] == "PUBLISHED"
    assert pub["data"].get("warningScanOk") is True
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=hdr).json()["data"]
    assert any(g["courseName"] == "发布一致课" and g["score"] == 87 and g["source"] == "PUBLISH"
               for g in tr["items"])
    # 重复发布
    again = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    assert again.status_code in (409, 400)


def test_bf6_import_midterm_and_class_guard(client, db_mode):
    """Excel 导入支持期中；非本班学生整批拒绝。"""
    sids, cid = _seed_students(1)
    hdr = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    other = StudentProfile(tenant_id=TID, student_no="OTHERBUG", real_name="外班", class_id=cid + 99999,
                           current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(other); db.commit(); db.close()
    tid = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "导入期中课", "termCode": "2026-1", "credit": 3, "classId": str(cid),
        "usualRatio": 30, "midtermRatio": 30, "finalRatio": 40,
        "adminSupplementReason": "测试管理员补录成绩任务"}).json()["data"]["gradeTaskId"]
    # 外班学生 → 整批 409
    bad = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "OTHERBUG", "usualScore": 80, "midtermScore": 80, "finalScore": 80}]})
    assert bad.status_code == 409
    # 缺期中 → 409
    miss = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "BUG000", "usualScore": 80, "finalScore": 80}]})
    assert miss.status_code == 409
    ok = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "BUG000", "usualScore": 80, "midtermScore": 90, "finalScore": 70}]})
    assert ok.status_code == 200, ok.text
    items = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"]
    assert items[0]["midtermScore"] == 90
