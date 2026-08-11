"""13B-R1 成绩审核发布更正 · 状态机/权限/数据范围/更正流程 端到端（真实 DB 模式）。

RF1 学院退回→重提→通过→发布 全链路；RF2 退回原因<5字422；RF3 教师跨范围403；
RF4 ACADEMIC_TEACHER 无教务终审权限(即使有academicAffairs.*通配)403；
RF5 归档后更正409；RF6 更正学院驳回原值不变；RF7 更正两级通过新值生效+source=CHANGE；
RF8 学生令牌全端点403。

历史测试曾用自由文本 termCode/courseName 创建管理员补录任务。当前正式合同要求管理员特殊补录
绑定真实 termId、稳定 courseId 和显式行政班名单；本文件夹具按生产合同补齐，不放宽后端门禁。
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
    college = College(tenant_id=TID, college_name="成绩审核学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="成绩审核专业", status="ACTIVE")
    db.add(major); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2602", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    seed_grade_review_identity(db, college_ids=[college.id])
    sids = []
    for i in range(n):
        s = StudentProfile(
            tenant_id=TID, student_no=f"RF{i:03d}", real_name=f"审核{i}",
            college_id=college.id, major_id=major.id, class_id=a.id,
            current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
        db.add(s); db.flush(); sids.append(s.id)
    db.commit()
    db.close()
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
    if not term:
        term = AaTerm(
            tenant_id=TID, year_code="2026-2027", term_no=1,
            term_name="2026-2027第1学期", teaching_weeks=18,
            status="PUBLISHED", is_current=True,
        )
        db.add(term); db.flush()
    else:
        term.status = "PUBLISHED"
        term.is_current = True
        term.teaching_weeks = int(term.teaching_weeks or 18)
    term_id = int(term.id)
    db.commit(); db.close()
    return term_id


def _ensure_course():
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    db = get_sessionmaker()()
    course = db.query(AaCourse).filter(
        AaCourse.tenant_id == TID,
        AaCourse.course_code == "RF101",
        AaCourse.is_deleted.is_(False),
    ).first()
    if not course:
        course = AaCourse(
            tenant_id=TID, course_code="RF101", course_name="大学物理",
            credit=3, nature="REQUIRED", category="MAJOR_CORE", status="ENABLED",
        )
        db.add(course); db.flush()
    else:
        course.status = "ENABLED"
    course_id = int(course.id)
    db.commit(); db.close()
    return course_id


def _class_id():
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass

    db = get_sessionmaker()()
    row = db.query(SchoolClass).filter(
        SchoolClass.tenant_id == TID,
        SchoolClass.class_name == "软件2602",
        SchoolClass.is_deleted.is_(False),
    ).order_by(SchoolClass.id.desc()).first()
    assert row is not None
    value = int(row.id)
    db.close()
    return value


def _task(client, hdr, usual=30, final=70):
    response = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "termId": str(_ensure_term()),
        "courseId": str(_ensure_course()),
        "courseName": "大学物理",
        "classId": str(_class_id()),
        "usualRatio": usual,
        "finalRatio": final,
        "adminSupplementReason": "测试管理员补录成绩任务，绑定正式学期课程与行政班",
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]["gradeTaskId"]


def test_rf1_return_resubmit_approve_publish(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 70, "finalScore": 80})
    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr).status_code == 200
    ret = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr,
                      json={"action": "RETURN", "reason": "分数需复核确认"})
    assert ret.status_code == 200 and ret.json()["data"]["status"] == "RETURNED"
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 75, "finalScore": 80})
    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr).status_code == 200
    appr = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    assert appr.status_code == 200 and appr.json()["data"]["status"] == "ACADEMIC_REVIEW"
    pub = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    assert pub.status_code == 200 and pub.json()["data"]["status"] == "PUBLISHED"


def test_rf2_return_reason_too_short_422(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 70, "finalScore": 80})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    r = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr,
                    json={"action": "RETURN", "reason": "短"})
    assert r.status_code in (400, 422)


def test_rf3_teacher_cross_course_scope_403(client, db_mode):
    """管理员建立的特殊补录任务，普通任课教师不得跨对象录入。"""
    sids = _seed(db_mode, 1)
    admin_hdr = _hdr(client, "school_admin01")
    tid = _task(client, admin_hdr)
    teacher_hdr = _hdr(client, "academic01")
    r = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=teacher_hdr,
                    json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    assert r.status_code == 403


def test_rf4_teacher_cannot_publish_even_with_wildcard_403(client, db_mode):
    """管理员把任务推进到学院审核通过后，ACADEMIC_TEACHER 仍不得做教务终审发布/归档。"""
    sids = _seed(db_mode, 1)
    admin_hdr = _hdr(client, "school_admin01")
    teacher_hdr = _hdr(client, "academic01")
    tid = _task(client, admin_hdr)
    entered = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=admin_hdr,
                          json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    assert entered.status_code == 200, entered.text
    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=admin_hdr).status_code == 200
    appr = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=admin_hdr,
                       json={"action": "APPROVE"})
    assert appr.status_code == 200 and appr.json()["data"]["status"] == "ACADEMIC_REVIEW"
    assert client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=teacher_hdr).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/{tid}/archive", headers=teacher_hdr).status_code == 403


def test_rf5_archived_change_request_409(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/archive", headers=hdr)
    from app.db.session import get_sessionmaker
    from app.models import AaGradeRecord
    db = get_sessionmaker()()
    rec = db.query(AaGradeRecord).filter(AaGradeRecord.task_id == int(tid)).first()
    assert rec is not None
    rid = int(rec.id)
    db.close()
    r = client.post(f"{BASE}/grade-tasks/{tid}/records/{rid}/change-request", headers=hdr,
                    json={"newFinalScore": 85, "reason": "重新核算成绩"})
    assert r.status_code == 409


def test_rf6_change_reject_keeps_original(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    from app.db.session import get_sessionmaker
    from app.models import AaGradeRecord
    db = get_sessionmaker()()
    rec = db.query(AaGradeRecord).filter(AaGradeRecord.task_id == int(tid)).first()
    assert rec is not None
    rid = int(rec.id)
    db.close()
    cr = client.post(f"{BASE}/grade-tasks/{tid}/records/{rid}/change-request", headers=hdr,
                     json={"newFinalScore": 60, "reason": "疑似录入错误需核实"})
    assert cr.status_code == 200, cr.text
    rj = client.post(f"{BASE}/grade-change/{rid}/college-review", headers=hdr,
                     json={"action": "REJECT", "reason": "核实后原分数无误"})
    assert rj.status_code == 200, rj.text
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=hdr).json()["data"]
    assert any(g["courseName"] == "大学物理" and g["score"] == 80 for g in tr["items"])


def test_rf7_change_two_level_approve_new_value_applied(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 60, "finalScore": 60})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    from app.db.session import get_sessionmaker
    from app.models import AaGradeRecord
    db = get_sessionmaker()()
    rec = db.query(AaGradeRecord).filter(AaGradeRecord.task_id == int(tid)).first()
    assert rec is not None
    rid = int(rec.id)
    db.close()
    client.post(f"{BASE}/grade-tasks/{tid}/records/{rid}/change-request", headers=hdr,
               json={"newFinalScore": 30, "reason": "复核发现期末分录入错误"})
    client.post(f"{BASE}/grade-change/{rid}/college-review", headers=hdr, json={"action": "APPROVE"})
    fin = client.post(f"{BASE}/grade-change/{rid}/academic-review", headers=hdr, json={"action": "APPROVE"})
    assert fin.status_code == 200, fin.text
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=hdr).json()["data"]
    row = next(g for g in tr["items"] if g["courseName"] == "大学物理")
    assert row["score"] == 39 and row["passStatus"] == "FAILED" and row["source"] == "CHANGE"


def test_rf8_student_forbidden_on_new_endpoints_403(client, db_mode):
    """越权红线：新增的提交/学院审/退回/归档/更正端点，学生令牌一律403。"""
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/grade-tasks/1/submit", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/1/college-review", headers=hdr, json={"action": "APPROVE"}).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/1/return", headers=hdr, json={"reason": "占位原因文本"}).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/1/archive", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/1/records/1/change-request", headers=hdr,
                       json={"reason": "占位原因文本"}).status_code == 403
    assert client.get(f"{BASE}/grade-tasks/1/roster", headers=hdr).status_code == 403
