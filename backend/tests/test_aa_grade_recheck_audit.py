"""教务中心「成绩审核发布更正」07/08 号三级补建：成绩复核 / 成绩操作审计 · 端到端（真实 MySQL）。

RA1 成绩明细复核：发布后 source=PUBLISH，更正两级通过后 source=CHANGE 且更正前值/原因/时间留痕；
RA2 审计正常路径：教务处角色可查全量，任务生命周期事件均可按 bizType 过滤查到；
RA3 审计数据范围：任课教师仅能自查本人操作，看不到其他教师的操作记录；
RA4 审计越权：学生令牌 403。

当前成绩任务必须绑定正式学期、课程版本和 READY 教学任务；成绩更正按学院初审/校级终审职责分离。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode, n=1):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile
    from tests.support_grade_review_identity import seed_grade_review_identity

    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name="成绩审计学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="成绩审计专业", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2603", grade="2026", status="ACTIVE")
    db.add(klass); db.flush()
    seed_grade_review_identity(db, college_ids=[college.id])
    sids = []
    for i in range(n):
        s = StudentProfile(
            tenant_id=TID, student_no=f"RA{i:03d}", real_name=f"复核{i}",
            college_id=college.id, major_id=major.id, class_id=klass.id,
            current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE",
        )
        db.add(s); db.flush(); sids.append(s.id)
    db.commit(); db.close()
    return sids


def _ensure_term():
    from app.db.session import get_sessionmaker
    from app.models import AaTerm

    db = get_sessionmaker()()
    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == TID,
        AaTerm.year_code == "2026-2027",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    ).first()
    if term is None:
        term = AaTerm(
            tenant_id=TID, year_code="2026-2027", term_no=1,
            term_name="2026-2027第1学期", teaching_weeks=18,
            status="PUBLISHED", is_current=True,
        )
        db.add(term); db.flush()
    else:
        term.status = "PUBLISHED"
        term.is_current = True
    term_id = int(term.id)
    db.commit(); db.close()
    return term_id


def _class_id():
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass

    db = get_sessionmaker()()
    row = db.query(SchoolClass).filter(
        SchoolClass.tenant_id == TID,
        SchoolClass.class_name == "软件2603",
        SchoolClass.is_deleted.is_(False),
    ).order_by(SchoolClass.id.desc()).first()
    assert row is not None
    value = int(row.id)
    db.close()
    return value


def _task(client, hdr, course_name="大学英语", owner_login="school_admin01", usual=30, final=70):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch

    term_id = _ensure_term()
    class_id = _class_id()
    db = get_sessionmaker()()
    seq = db.query(AaCourse).filter(AaCourse.tenant_id == TID).count() + 1
    course = AaCourse(
        tenant_id=TID, course_code=f"RA{seq:04d}", course_name=course_name,
        credit=3, status="ENABLED",
    )
    db.add(course); db.flush()
    batch = AaTeachingTaskBatch(
        tenant_id=TID, term_id=term_id, batch_name=f"{course_name}教学任务批次", status="APPROVED",
    )
    db.add(batch); db.flush()
    task = AaTeachingTask(
        tenant_id=TID, batch_id=batch.id,
        course_id=course.id, course_code=course.course_code, course_name=course.course_name,
        class_id=class_id, teaching_class_name="软件2603",
        teacher_key=owner_login, teacher_name=owner_login,
        weekly_hours=4, start_week=1, end_week=18, status="READY",
    )
    db.add(task); db.flush()
    task_id = int(task.id)
    db.commit(); db.close()

    response = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(task_id), "usualRatio": usual, "finalRatio": final,
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]["gradeTaskId"]


def test_ra1_records_show_source_and_change_history(client, db_mode):
    sids = _seed(db_mode, 1)
    school_hdr = _hdr(client, "school_admin01")
    college_hdr = _hdr(client, "college_admin01")
    tid = _task(client, school_hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=school_hdr,
               json={"studentId": str(sids[0]), "usualScore": 70, "finalScore": 80})
    before = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=school_hdr).json()["data"]["items"]
    assert len(before) == 1
    rec0 = before[0]
    assert rec0["recordId"] and rec0["totalScore"] == 77 and rec0["source"] != "PUBLISH"
    assert rec0["prevTotalScore"] is None and rec0["changeReason"] == "" and rec0["versionNo"] == 1

    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=school_hdr).status_code == 200
    assert client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=school_hdr,
                       json={"action": "APPROVE"}).status_code == 200
    pub = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=school_hdr)
    assert pub.status_code == 200, pub.text
    after_publish = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=school_hdr).json()["data"]["items"][0]
    assert after_publish["source"] == "PUBLISH"

    rid = after_publish["recordId"]
    cr = client.post(f"{BASE}/grade-tasks/{tid}/records/{rid}/change-request", headers=school_hdr,
                     json={"newFinalScore": 90, "reason": "复核发现期末分登记错误"})
    assert cr.status_code == 200, cr.text
    college = client.post(f"{BASE}/grade-change/{rid}/college-review", headers=college_hdr,
                          json={"action": "APPROVE"})
    assert college.status_code == 200, college.text
    fin = client.post(f"{BASE}/grade-change/{rid}/academic-review", headers=school_hdr,
                      json={"action": "APPROVE"})
    assert fin.status_code == 200, fin.text

    after_change = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=school_hdr).json()["data"]["items"][0]
    assert after_change["recordId"] == rid
    assert after_change["source"] == "CHANGE"
    assert after_change["totalScore"] == 84
    assert after_change["prevTotalScore"] == 77
    assert after_change["changeReason"] == "复核发现期末分登记错误"
    assert after_change["changeAt"]
    assert after_change["versionNo"] == 2


def test_ra2_audit_full_lifecycle_visible_to_academic_admin_with_biztype_filter(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr, course_name="审计用课程")
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    exp = client.post(f"{BASE}/students/{sids[0]}/transcript/export", headers=hdr,
                      json={"purpose": "测试审计过滤"})
    assert exp.status_code == 200, exp.text

    r_all = client.get(f"{BASE}/grade-views/audit", headers=hdr, params={"pageSize": 100})
    assert r_all.status_code == 200, r_all.text
    all_items = r_all.json()["data"]["items"]
    task_actions = {it["action"] for it in all_items if it["bizId"] == tid and it["bizType"] == "AA_GRADE_TASK"}
    assert {"CREATE", "ENTER", "SUBMIT"}.issubset(task_actions)
    assert any(it["bizType"] == "AA_GRADE_TRANSCRIPT" and it["action"] == "EXPORT" for it in all_items)
    assert all(it["detail"] == "审计用课程" for it in all_items if it["action"] == "CREATE" and it["bizId"] == tid)

    r_task_only = client.get(f"{BASE}/grade-views/audit", headers=hdr,
                             params={"bizType": "AA_GRADE_TASK", "pageSize": 100})
    assert r_task_only.status_code == 200
    task_only_items = r_task_only.json()["data"]["items"]
    assert len(task_only_items) >= 3
    assert all(it["bizType"] == "AA_GRADE_TASK" for it in task_only_items)

    r_transcript_only = client.get(f"{BASE}/grade-views/audit", headers=hdr,
                                   params={"bizType": "AA_GRADE_TRANSCRIPT", "pageSize": 100})
    assert r_transcript_only.status_code == 200
    transcript_items = r_transcript_only.json()["data"]["items"]
    assert len(transcript_items) == 1 and transcript_items[0]["action"] == "EXPORT"


def test_ra3_teacher_sees_only_own_operator_audit_rows(client, db_mode):
    _seed(db_mode, 1)
    teacher_hdr = _hdr(client, "academic01")
    admin_hdr = _hdr(client, "school_admin01")
    own_tid = _task(client, teacher_hdr, course_name="教师自建课程", owner_login="academic01")
    other_tid = _task(client, admin_hdr, course_name="管理员建的课程", owner_login="school_admin01")
    assert own_tid != other_tid

    r = client.get(f"{BASE}/grade-views/audit", headers=teacher_hdr,
                   params={"bizType": "AA_GRADE_TASK", "pageSize": 100})
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert any(it["bizId"] == own_tid and it["action"] == "CREATE" for it in items)
    assert all(it["bizId"] != other_tid for it in items)
    assert all(it["operator"] == "赵敏" for it in items)


def test_ra4_student_forbidden_on_audit_endpoint_403(client, db_mode):
    hdr = _hdr(client, "student01")
    r = client.get(f"{BASE}/grade-views/audit", headers=hdr)
    assert r.status_code == 403
