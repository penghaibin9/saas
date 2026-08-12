"""教务中心 Bug 修复回归：学分小数 / 期中回显 / 成绩任务去重 / 发布后成绩单一致。

成绩相关回归统一走正式学期、课程版本、READY 教学任务和行政班名单，不再用自由 termCode/courseName
或不存在的 course_id 绕过当前生产身份门禁。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_students(n=1):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, College, Major, SchoolClass, StudentProfile
    from tests.support_grade_review_identity import seed_grade_review_identity

    db = get_sessionmaker()()
    term = AaTerm(
        tenant_id=TID, year_code="2026-2027", term_no=1,
        term_name="2026-2027第1学期", teaching_weeks=18,
        status="PUBLISHED", is_current=True,
    )
    db.add(term); db.flush()
    college = College(tenant_id=TID, college_name="BUG回归学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="BUG回归专业", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件BUG01", grade="2026", status="ACTIVE")
    db.add(klass); db.flush()
    seed_grade_review_identity(db, college_ids=[college.id])
    sids = []
    for i in range(n):
        s = StudentProfile(
            tenant_id=TID, student_no=f"BUG{i:03d}", real_name=f"修{i}",
            college_id=college.id, major_id=major.id, class_id=klass.id,
            current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE",
        )
        db.add(s); db.flush(); sids.append(s.id)
    db.commit()
    cid, term_id = int(klass.id), int(term.id)
    db.close()
    return sids, cid, term_id


def _teaching_task(term_id, class_id, course_name, *, credit=3, owner="school_admin01"):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch

    db = get_sessionmaker()()
    seq = db.query(AaCourse).filter(AaCourse.tenant_id == TID).count() + 1
    course = AaCourse(
        tenant_id=TID, course_code=f"BUG{seq:04d}", course_name=course_name,
        credit=credit, status="ENABLED",
    )
    db.add(course); db.flush()
    batch = AaTeachingTaskBatch(
        tenant_id=TID, term_id=int(term_id), batch_name=f"{course_name}教学任务批次", status="APPROVED",
    )
    db.add(batch); db.flush()
    task = AaTeachingTask(
        tenant_id=TID, batch_id=batch.id,
        course_id=course.id, course_code=course.course_code, course_name=course.course_name,
        class_id=int(class_id), teaching_class_name="软件BUG01",
        teacher_key=owner, teacher_name=owner,
        weekly_hours=4, start_week=1, end_week=18, status="READY",
    )
    db.add(task); db.flush()
    task_id = int(task.id)
    db.commit(); db.close()
    return task_id


def test_bf1_program_half_credit_persists(client, db_mode):
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
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "二点五学分课", "credit": 2.5, "openTermNo": 2})
    detail2 = client.get(f"{BASE}/programs/{pid}", headers=hdr).json()["data"]
    courses2 = detail2.get("courses") or detail2.get("courseItems") or []
    assert any(float(c.get("credit") if c.get("credit") is not None else c.get("creditSnapshot")) == 2.5
               for c in courses2 if c.get("courseName") == "二点五学分课")


def test_bf2_midterm_persists_on_list_records(client, db_mode):
    sids, cid, term_id = _seed_students(1)
    hdr = _hdr(client, "school_admin01")
    tt_id = _teaching_task(term_id, cid, "期中回显课")
    created = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(tt_id),
        "usualRatio": 30, "midtermRatio": 30, "finalRatio": 40,
    })
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["gradeTaskId"]
    r = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={
        "studentId": str(sids[0]), "usualScore": 80, "midtermScore": 90, "finalScore": 70})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["midtermScore"] == 90
    assert r.json()["data"]["totalScore"] == 79
    items = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"]
    assert items[0]["midtermScore"] == 90
    assert items[0]["usualScore"] == 80
    assert items[0]["finalScore"] == 70


def test_bf3_duplicate_grade_task_same_teaching_task_409(client, db_mode):
    _sids, cid, term_id = _seed_students(0)
    hdr = _hdr(client, "school_admin01")
    tt_id = _teaching_task(term_id, cid, "去重课")
    r1 = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(tt_id), "usualRatio": 30, "finalRatio": 70})
    assert r1.status_code == 200, r1.text
    r2 = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(tt_id), "usualRatio": 30, "finalRatio": 70})
    assert r2.status_code == 409, r2.text


def test_bf4_teacher_must_bind_teaching_task(client, db_mode):
    teacher_hdr = _hdr(client, "academic01")
    r = client.post(f"{BASE}/grade-tasks", headers=teacher_hdr, json={
        "courseName": "脱离教学任务", "usualRatio": 30, "finalRatio": 70})
    assert r.status_code in (400, 422)


def test_bf5_publish_then_transcript_consistent(client, db_mode):
    sids, cid, term_id = _seed_students(1)
    hdr = _hdr(client, "school_admin01")
    tt_id = _teaching_task(term_id, cid, "发布一致课", credit=3.5)
    created = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(tt_id), "usualRatio": 30, "finalRatio": 70,
    })
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["gradeTaskId"]
    entered = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={
        "studentId": str(sids[0]), "usualScore": 80, "finalScore": 90})
    assert entered.status_code == 200, entered.text
    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr).status_code == 200
    assert client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr,
                       json={"action": "APPROVE"}).status_code == 200
    pub_resp = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    assert pub_resp.status_code == 200, pub_resp.text
    pub = pub_resp.json()
    assert pub["data"]["status"] == "PUBLISHED"
    assert pub["data"].get("warningScanOk") is True
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=hdr).json()["data"]
    assert any(g["courseName"] == "发布一致课" and g["score"] == 87 and g["source"] == "PUBLISH"
               for g in tr["items"])
    again = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    assert again.status_code in (409, 400)


def test_bf6_import_midterm_and_class_guard(client, db_mode):
    sids, cid, term_id = _seed_students(1)
    hdr = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    other = StudentProfile(
        tenant_id=TID, student_no="OTHERBUG", real_name="外班", class_id=cid + 99999,
        current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE",
    )
    db.add(other); db.commit(); db.close()
    tt_id = _teaching_task(term_id, cid, "导入期中课")
    created = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(tt_id),
        "usualRatio": 30, "midtermRatio": 30, "finalRatio": 40,
    })
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["gradeTaskId"]

    bad = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "OTHERBUG", "usualScore": 80, "midtermScore": 80, "finalScore": 80}]})
    assert bad.status_code == 409
    miss = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "BUG000", "usualScore": 80, "finalScore": 80}]})
    assert miss.status_code == 409
    ok = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "BUG000", "usualScore": 80, "midtermScore": 90, "finalScore": 70}]})
    assert ok.status_code == 200, ok.text
    items = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"]
    assert items[0]["midtermScore"] == 90
