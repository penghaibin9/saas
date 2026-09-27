"""13B-P3 培养方案发布 + 教学任务全链 · 端到端。

历史用例已对齐当前权威合同：真实 College→Major→Class、正式学期时间轴/教学周、
稳定课程身份、ENABLED 培养方案和 ACTIVE 班级绑定。课程开课学院与学生学院独立，
学院分配、正式任课教师确认、学院确认、学校终审使用各自身份，业务断言保持原强度。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from tests.support_academic_review_identity import ensure_college_review_scope, ensure_course_review_college
from tests.support_task_review_identity import ensure_task_review_identity

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode, *, grade="2026", two=False):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass

    db = get_sessionmaker()()
    seq = db.query(College).filter(College.tenant_id == TID).count() + 1
    college = College(tenant_id=TID, college_name=f"教学任务回归学院{seq}", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id,
                  major_name=f"教学任务软件技术{seq}", status="ACTIVE")
    db.add(major); db.flush()
    year2 = grade[-2:]
    a = SchoolClass(tenant_id=TID, major_id=major.id,
                    class_name=f"软件{year2}01", grade=grade, status="ACTIVE")
    db.add(a); db.flush()
    ids = {"college": int(college.id), "major": int(major.id), "class": int(a.id),
           "class1": int(a.id)}
    if two:
        b = SchoolClass(tenant_id=TID, major_id=major.id,
                        class_name=f"软件{year2}02", grade=grade, status="ACTIVE")
        db.add(b); db.flush()
        ids["class2"] = int(b.id)
    db.commit(); db.close()
    return ids


def _seed_two_classes(db_mode, *, grade="2026"):
    return _seed(db_mode, grade=grade, two=True)


def _enabled_course(client, hdr, code="TT101", credit=4, name="程序设计"):
    owner_college_id = ensure_course_review_college()
    ensure_task_review_identity(owner_college_id)
    created = client.post(f"{BASE}/courses", headers=hdr, json={
        "courseCode": code, "courseName": name, "category": "MAJOR_CORE", "nature": "REQUIRED",
        "credit": credit, "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16,
        "examMode": "EXAM", "ownerCollegeId": str(owner_college_id)})
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["courseId"]
    submitted = client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    assert submitted.status_code == 200, submitted.text
    college = client.post(
        f"{BASE}/courses/{cid}/review",
        headers=_hdr(client, "college_admin01"),
        json={"action": "APPROVE"},
    )
    assert college.status_code == 200, college.text
    academic = client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    assert academic.status_code == 200, academic.text
    return cid


def _program(client, hdr, *, major_id, grade_year, total_credits, courses, bindings, name):
    ensure_college_review_scope(major_ids=[major_id])
    created = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": name, "majorId": str(major_id), "gradeYear": grade_year,
        "totalCredits": total_credits})
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["programId"]
    for course_id, course_name, credit, open_term_no in courses:
        added = client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
            "courseId": str(course_id), "courseName": course_name,
            "openTermNo": open_term_no, "module": "专业核心", "credit": credit})
        assert added.status_code == 200, added.text
    from tests.support_program_quality_fixture import seed_program_quality_requirements
    seed_program_quality_requirements(pid, total_credits=total_credits)
    submitted = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert submitted.status_code == 200, submitted.text
    college = client.post(
        f"{BASE}/programs/{pid}/review",
        headers=_hdr(client, "college_admin01"),
        json={"action": "APPROVE"},
    )
    assert college.status_code == 200, college.text
    academic = client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    assert academic.status_code == 200, academic.text
    for binding_grade, class_id in bindings:
        body = {"gradeYear": binding_grade}
        if class_id is not None:
            body["classId"] = str(class_id)
        bound = client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json=body)
        assert bound.status_code == 200, bound.text
    return pid


def _published_bound_program(client, hdr, course_id, class_id, major_id, total=4,
                             *, grade_year="2026"):
    return _program(
        client, hdr, major_id=major_id, grade_year=grade_year, total_credits=total,
        courses=[(course_id, "程序设计", 4, 1)], bindings=[(grade_year, class_id)],
        name=f"软件技术{grade_year}方案",
    )


def _term(client, hdr, *, year_code="2026-2027", term_no=1):
    """正式教学任务学期：稳定时间轴 + 18 教学周 + 发布态，并准备正式节次供 TT11 排课事实使用。"""
    start_year = int(year_code[:4])
    start = date(start_year, 9, 1) if term_no == 1 else date(start_year + 1, 2, 20)
    created = client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": year_code, "termNo": term_no,
        "termName": f"{year_code}第{term_no}学期",
        "startDate": start.isoformat(), "endDate": (start + timedelta(days=140)).isoformat(),
        "teachingWeeks": 18,
    })
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["termId"]
    published = client.post(f"{BASE}/terms/{tid}/publish", headers=hdr)
    assert published.status_code == 200, published.text

    from app.db.session import get_sessionmaker
    from app.models import AaTimeSlot
    db = get_sessionmaker()()
    times = {1: ("08:00", "08:45"), 2: ("08:55", "09:40")}
    for slot_no, (start_time, end_time) in times.items():
        row = db.query(AaTimeSlot).filter(
            AaTimeSlot.tenant_id == TID, AaTimeSlot.slot_no == slot_no,
            AaTimeSlot.is_deleted.is_(False)).first()
        if row is None:
            db.add(AaTimeSlot(tenant_id=TID, slot_no=slot_no, slot_name=f"第{slot_no}节",
                              start_time=start_time, end_time=end_time,
                              enabled=True, status="ENABLED"))
        else:
            row.start_time, row.end_time = start_time, end_time
            row.enabled, row.status = True, "ENABLED"
    db.commit(); db.close()
    return tid


def _generate(client, hdr, term_id):
    # 所有 _enabled_course 创建的课程属于该开课学院；学生所在学院保持独立。
    owner_college_id = ensure_course_review_college()
    response = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                           json={"termId": str(term_id), "collegeId": str(owner_college_id)})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _tasks(client, hdr, batch_id):
    response = client.get(f"{BASE}/teaching-task-batches/{batch_id}/tasks", headers=hdr)
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


def test_tt1_full_chain(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr)
    _published_bound_program(client, hdr, cid, ids["class"], ids["major"])
    tid = _term(client, hdr)
    g = _generate(client, hdr, tid)
    assert g["tasksGenerated"] == 1
    bid = g["batchId"]
    tasks = _tasks(client, hdr, bid)
    task_id = tasks[0]["taskId"]
    assert tasks[0]["weeklyHours"]
    assert client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr,
                       json={"teacherName": "赵敏", "teacherKey": "academic01"}).status_code == 403
    assigned = client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=_hdr(client, "college_admin01"),
                           json={"teacherName": "赵敏", "teacherKey": "academic01", "expectedStudents": 40})
    assert assigned.status_code == 200, assigned.text
    r = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=_hdr(client, "academic01"),
                    json={"action": "CONFIRM"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "TEACHER_CONFIRMED"
    b = client.post(f"{BASE}/teaching-task-batches/{bid}/submit", headers=_hdr(client, "college_admin01"))
    assert b.status_code == 200, b.text
    assert b.json()["data"]["status"] == "COLLEGE_CONFIRMED"
    reviewed = client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr,
                           json={"action": "APPROVE"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["status"] == "APPROVED"
    assert _tasks(client, hdr, bid)[0]["status"] == "READY"


def test_tt2_generate_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr)
    _published_bound_program(client, hdr, cid, ids["class"], ids["major"])
    tid = _term(client, hdr)
    g1 = _generate(client, hdr, tid)
    assert g1["tasksGenerated"] == 1
    g2 = _generate(client, hdr, tid)
    assert g2["tasksGenerated"] == 0


def test_generation_rejects_binding_created_after_historical_term_end(client, db_mode):
    ids = _seed(db_mode, grade="2020")
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT-HISTORY-LATE")
    _program(client, hdr, major_id=ids["major"], grade_year="2020", total_credits=4,
             courses=[(cid, "程序设计", 4, 1)],
             bindings=[("2020", ids["class"])], name="历史晚绑定方案")
    tid = _term(client, hdr, year_code="2020-2021")

    rejected = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                           json={"termId": str(tid), "collegeId": str(ensure_course_review_college())})
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["bizCode"] == "DATA_CONFLICT"
    assert "学期结束时尚未生效" in rejected.json()["message"]

    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskBatch

    with get_sessionmaker()() as db:
        assert db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.tenant_id == TID,
            AaTeachingTaskBatch.term_id == int(tid),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).count() == 0


def test_generation_accepts_binding_effective_before_term_end(client, db_mode):
    ids = _seed(db_mode, grade="2041")
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT-HISTORY-VALID")
    _program(client, hdr, major_id=ids["major"], grade_year="2041", total_credits=4,
             courses=[(cid, "程序设计", 4, 1)],
             bindings=[("2041", ids["class"])], name="期内绑定方案")
    tid = _term(client, hdr, year_code="2041-2042")

    generated = _generate(client, hdr, tid)
    assert generated["tasksGenerated"] == 1
    assert len(_tasks(client, hdr, generated["batchId"])) == 1


def test_generation_rejects_current_binding_when_another_version_was_effective_at_term_end(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as generation

    old = SimpleNamespace(program=SimpleNamespace(id=11), binding=SimpleNamespace(id=101),
                          status="RESOLVED", rule="CLASS_HISTORICAL_EFFECTIVE")
    current = SimpleNamespace(program=SimpleNamespace(id=12), binding=SimpleNamespace(id=102),
                              status="RESOLVED", rule="CLASS_BINDING")
    observed = []

    def resolve(_db, **kwargs):
        observed.append(kwargs.get("as_of"))
        return old if "as_of" in kwargs else current

    monkeypatch.setattr(generation, "_tid", lambda: TID)
    monkeypatch.setattr(generation.program_activation, "resolve_program_for_scope", resolve)
    with pytest.raises(AppException) as rejected:
        generation._resolve_binding_for_class(
            object(), current.program, current.binding,
            SimpleNamespace(id=4668, major_id=9, grade="2023", class_name="甲班"),
            term_end=datetime(2026, 7, 12),
        )
    assert rejected.value.http_status == 409
    assert rejected.value.details["blocker"] == "PROGRAM_BINDING_NOT_EFFECTIVE_AT_TERM_END"
    assert observed == [None, datetime(2026, 7, 12)]


def test_tt3_program_credit_shortfall_blocks_submit(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT301")
    created = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "学分不足方案", "majorId": str(ids["major"]),
        "gradeYear": "2026", "totalCredits": 120})
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["programId"]
    added = client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(cid), "courseName": "程序设计", "openTermNo": 1,
        "module": "专业核心", "credit": 4})
    assert added.status_code == 200, added.text
    from tests.support_program_quality_fixture import seed_program_quality_requirements
    seed_program_quality_requirements(pid, total_credits=120)
    blocked = client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    assert blocked.status_code == 409, blocked.text
    payload = blocked.json()
    assert payload["bizCode"] == "PROGRAM_VALIDATION_BLOCKED"
    assert "课程与实践学分合计" in payload["message"] and "毕业总学分 120" in payload["message"]


def test_tt4_batch_submit_with_unassigned_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT401")
    _published_bound_program(client, hdr, cid, ids["class"], ids["major"])
    bid = _generate(client, hdr, _term(client, hdr))["batchId"]
    assert client.post(f"{BASE}/teaching-task-batches/{bid}/submit", headers=_hdr(client, "college_admin01")).status_code == 409


def test_tt5_two_level_confirm_approve_ready(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT501")
    _published_bound_program(client, hdr, cid, ids["class"], ids["major"])
    bid = _generate(client, hdr, _term(client, hdr))["batchId"]
    task_id = _tasks(client, hdr, bid)[0]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=_hdr(client, "college_admin01"),
                json={"teacherName": "赵敏", "teacherKey": "academic01", "expectedStudents": 40})
    client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=_hdr(client, "academic01"), json={"action": "CONFIRM"})
    cc = client.post(f"{BASE}/teaching-task-batches/{bid}/college-confirm", headers=_hdr(client, "college_admin01"))
    assert cc.status_code == 200 and cc.json()["data"]["status"] == "COLLEGE_CONFIRMED"
    rv = client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr, json={"action": "APPROVE"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "APPROVED"
    assert _tasks(client, hdr, bid)[0]["status"] == "READY"
    stats = client.get(f"{BASE}/teaching-task-batches/stats", headers=hdr).json()["data"]
    assert stats["taskByStatus"].get("READY") == 1
    assert stats["assignRate"]["numerator"] == 1 and stats["teacherConfirmRate"]["numerator"] == 1


def test_tt6_review_return_then_reconfirm(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT601")
    _published_bound_program(client, hdr, cid, ids["class"], ids["major"])
    bid = _generate(client, hdr, _term(client, hdr))["batchId"]
    task_id = _tasks(client, hdr, bid)[0]["taskId"]
    assigned = client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=_hdr(client, "college_admin01"),
                           json={"teacherName": "赵敏", "teacherKey": "academic01"})
    assert assigned.status_code == 200, assigned.text
    confirmed = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=_hdr(client, "academic01"),
                            json={"action": "CONFIRM"})
    assert confirmed.status_code == 200, confirmed.text
    assert client.post(f"{BASE}/teaching-task-batches/{bid}/college-confirm", headers=_hdr(client, "college_admin01")).status_code == 200
    bad = client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr,
                      json={"action": "RETURN", "reason": "短"})
    assert bad.status_code == 400
    rv = client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr,
                     json={"action": "RETURN", "reason": "教师工作量超限需重新安排"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "RETURNED"
    assert client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr,
                       json={"action": "APPROVE"}).status_code == 409
    again = client.post(f"{BASE}/teaching-task-batches/{bid}/college-confirm", headers=_hdr(client, "college_admin01"))
    assert again.status_code == 200 and again.json()["data"]["status"] == "COLLEGE_CONFIRMED"


def test_tt7_merge_then_split(client, db_mode):
    ids = _seed_two_classes(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT701")
    _program(client, hdr, major_id=ids["major"], grade_year="2026", total_credits=4,
             courses=[(cid, "程序设计", 4, 1)],
             bindings=[("2026", None)], name="合班测试方案")
    g = _generate(client, hdr, _term(client, hdr))
    assert g["tasksGenerated"] == 2
    bid = g["batchId"]
    tasks = _tasks(client, hdr, bid)
    t1, t2 = tasks[0]["taskId"], tasks[1]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{t1}/assign", headers=_hdr(client, "college_admin01"),
                json={"teacherName": "赵敏", "teacherKey": "academic01", "expectedStudents": 20})
    client.post(f"{BASE}/teaching-tasks/{t2}/assign", headers=_hdr(client, "college_admin01"),
                json={"teacherName": "赵敏", "teacherKey": "academic01", "expectedStudents": 25})
    assert client.post(f"{BASE}/teaching-tasks/merge", headers=hdr,
                       json={"taskIds": [t1, t2]}).status_code == 403
    m = client.post(f"{BASE}/teaching-tasks/merge", headers=_hdr(client, "college_admin01"),
                    json={"taskIds": [t1, t2], "note": "小班合并授课"})
    assert m.status_code == 200
    survivor = m.json()["data"]
    assert survivor["taskId"] == t1 and survivor["isMerged"] is True and survivor["expectedStudents"] == 45
    after_merge = {r["taskId"]: r for r in _tasks(client, hdr, bid)}
    assert after_merge[t2]["status"] == "MERGED" and after_merge[t2]["mergedIntoId"] == t1
    assert client.post(f"{BASE}/teaching-tasks/{t1}/split", headers=hdr).status_code == 403
    s = client.post(f"{BASE}/teaching-tasks/{t1}/split", headers=_hdr(client, "college_admin01"))
    assert s.status_code == 200
    split_row = s.json()["data"]
    assert split_row["isMerged"] is False and split_row["expectedStudents"] == 20
    after_split = {r["taskId"]: r for r in _tasks(client, hdr, bid)}
    assert after_split[t2]["status"] == "PENDING_ASSIGN" and after_split[t2]["expectedStudents"] == 25


def test_tt8_merge_validation(client, db_mode):
    ids = _seed_two_classes(db_mode)
    hdr = _hdr(client, "school_admin01")
    c1 = _enabled_course(client, hdr, code="TT801")
    c2 = _enabled_course(client, hdr, code="TT802")
    _program(client, hdr, major_id=ids["major"], grade_year="2026", total_credits=8,
             courses=[(c1, "课程", 4, 1), (c2, "课程", 4, 1)],
             bindings=[("2026", ids["class1"])], name="跨课程校验方案")
    g = _generate(client, hdr, _term(client, hdr))
    assert g["tasksGenerated"] == 2
    bid = g["batchId"]
    tasks = _tasks(client, hdr, bid)
    t1, t2 = tasks[0]["taskId"], tasks[1]["taskId"]
    assert client.post(f"{BASE}/teaching-tasks/merge", headers=_hdr(client, "college_admin01"),
                       json={"taskIds": [t1]}).status_code == 400
    assert client.post(f"{BASE}/teaching-tasks/merge", headers=_hdr(client, "college_admin01"),
                       json={"taskIds": [t1, t2]}).status_code == 400

    ids2 = _seed_two_classes(db_mode, grade="2027")
    cid3 = _enabled_course(client, hdr, code="TT803")
    _program(client, hdr, major_id=ids2["major"], grade_year="2027", total_credits=4,
             courses=[(cid3, "课程", 4, 1)], bindings=[("2027", None)],
             name="重复合并校验方案")
    g2 = _generate(client, hdr, _term(client, hdr, year_code="2027-2028"))
    bid2 = g2["batchId"]
    cid3_tasks = [r["taskId"] for r in _tasks(client, hdr, bid2) if r["courseId"] == str(cid3)]
    assert len(cid3_tasks) == 2
    t3, t4 = cid3_tasks
    assert client.post(f"{BASE}/teaching-tasks/merge", headers=_hdr(client, "college_admin01"),
                       json={"taskIds": [t3, t4]}).status_code == 200
    dup = client.post(f"{BASE}/teaching-tasks/merge", headers=_hdr(client, "college_admin01"), json={"taskIds": [t3, t4]})
    assert dup.status_code == 409


def test_tt9_cross_batch_list_and_teacher_scope(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT901")
    _published_bound_program(client, hdr, cid, ids["class"], ids["major"])
    bid = _generate(client, hdr, _term(client, hdr))["batchId"]
    task_id = _tasks(client, hdr, bid)[0]["taskId"]
    mergeable = client.get(f"{BASE}/teaching-tasks", headers=hdr,
                           params={"mergeable": True}).json()["data"]["items"]
    assert any(r["taskId"] == task_id for r in mergeable)
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=_hdr(client, "college_admin01"),
                json={"teacherName": "赵敏", "teacherKey": "academic01"})
    other_hdr = _hdr(client, "teacher01")
    forbidden = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=other_hdr,
                            json={"action": "CONFIRM"})
    assert forbidden.status_code == 403
    self_hdr = _hdr(client, "academic01")
    ok = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=self_hdr,
                     json={"action": "CONFIRM"})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "TEACHER_CONFIRMED"
    mine = client.get(f"{BASE}/teaching-tasks", headers=self_hdr,
                      params={"mine": True}).json()["data"]["items"]
    assert any(r["taskId"] == task_id for r in mine)


def test_tt10_adjust_task_partial_update_and_teacher_reconfirm(client, db_mode, monkeypatch):
    # This isolated test adds a second explicit mock-login identity; unknown login names otherwise fall back to a different teacher.
    from app.services import mock_auth_service
    teacher = mock_auth_service._mk_user("u_academic02", "academic02", "李老师", "TEACHER",
        "ACADEMIC_TEACHER", "任课教师", "开课学院", "SELF", "本人任课任务")
    monkeypatch.setitem(mock_auth_service.DEMO_USERS, "u_academic02", teacher)
    monkeypatch.setitem(mock_auth_service._LOGIN_INDEX, "academic02", "u_academic02")
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT1001")
    _published_bound_program(client, hdr, cid, ids["class"], ids["major"])
    bid = _generate(client, hdr, _term(client, hdr))["batchId"]
    college_hdr = _hdr(client, "college_admin01")
    teacher_hdr = _hdr(client, "academic01")
    task_id = _tasks(client, hdr, bid)[0]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=college_hdr,
                json={"teacherName": "赵敏", "teacherKey": "academic01", "expectedStudents": 40})
    client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=teacher_hdr,
                json={"action": "CONFIRM"})
    assert client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=hdr,
                       json={"weeklyHours": 5, "reason": "学校不可无代理代办"}).status_code == 403
    bad = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=college_hdr,
                      json={"weeklyHours": 5, "reason": "短"})
    assert bad.status_code == 400
    r1 = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=college_hdr,
                     json={"weeklyHours": 6, "totalHours": 108, "reason": "教学计划课时数校正"})
    assert r1.status_code == 200
    d1 = r1.json()["data"]
    assert d1["weeklyHours"] == 6 and d1["totalHours"] == 108 and d1["status"] == "TEACHER_CONFIRMED"
    noop = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=college_hdr,
                       json={"weeklyHours": 6, "reason": "重复提交校验"})
    assert noop.status_code == 400
    for path, headers, payload in [
        (f"teaching-task-batches/{bid}/college-confirm", college_hdr, None),
        (f"teaching-task-batches/{bid}/review", hdr, {"action": "APPROVE"}),
    ]:
        approved = client.post(f"{BASE}/{path}", headers=headers, json=payload)
        assert approved.status_code == 200, approved.text
    assert _tasks(client, hdr, bid)[0]["status"] == "READY"
    r2 = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=college_hdr,
                     json={"teacherName": "李老师", "teacherKey": "academic02", "reason": "原教师休产假换人代课"})
    assert r2.status_code == 200
    d2 = r2.json()["data"]
    assert d2["teacherName"] == "李老师" and d2["status"] == "ASSIGNED"

    workbench = client.get(f"{BASE}/teaching-task-batches/{bid}/workbench", headers=college_hdr)
    assert workbench.status_code == 200, workbench.text
    assert workbench.json()["data"]["status"] == "RETURNED"
    old = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=teacher_hdr, json={"action": "CONFIRM"})
    assert old.status_code == 403, old.text
    for path, headers, payload in [
        (f"teaching-tasks/{task_id}/teacher-act", _hdr(client, "academic02"), {"action": "CONFIRM"}),
        (f"teaching-task-batches/{bid}/college-confirm", college_hdr, None),
        (f"teaching-task-batches/{bid}/review", hdr, {"action": "APPROVE"}),
    ]:
        advanced = client.post(f"{BASE}/{path}", headers=headers, json=payload)
        assert advanced.status_code == 200, advanced.text
    assert _tasks(client, hdr, bid)[0]["status"] == "READY"
    renamed = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=college_hdr,
                          json={"teacherName": "李老师姓名校正", "reason": "仅校正教师显示姓名"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["status"] == "READY"
    refreshed = client.get(f"{BASE}/teaching-task-batches/{bid}/workbench", headers=college_hdr)
    assert refreshed.json()["data"]["status"] == "APPROVED"



def test_tt11_adjust_task_conflicts_and_permission(client, db_mode):
    ids = _seed_two_classes(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT1101")
    _program(client, hdr, major_id=ids["major"], grade_year="2026", total_credits=4,
             courses=[(cid, "程序设计", 4, 1)], bindings=[("2026", None)],
             name="调整校验方案")
    tid = _term(client, hdr)
    g = _generate(client, hdr, tid)
    bid = g["batchId"]
    college_hdr = _hdr(client, "college_admin01")
    teacher_hdr = _hdr(client, "academic01")
    tasks = _tasks(client, hdr, bid)
    t1, t2 = tasks[0]["taskId"], tasks[1]["taskId"]
    a1 = client.post(f"{BASE}/teaching-tasks/{t1}/assign", headers=college_hdr,
                     json={"teacherName": "赵敏", "teacherKey": "academic01"})
    a2 = client.post(f"{BASE}/teaching-tasks/{t2}/assign", headers=college_hdr,
                     json={"teacherName": "赵敏", "teacherKey": "academic01"})
    assert a1.status_code == 200 and a2.status_code == 200
    merged = client.post(f"{BASE}/teaching-tasks/merge", headers=college_hdr, json={"taskIds": [t1, t2]})
    assert merged.status_code == 200, merged.text
    merged_adjust = client.post(f"{BASE}/teaching-tasks/{t2}/adjust", headers=college_hdr,
                                json={"weeklyHours": 4, "reason": "尝试调整已并入成员任务"})
    assert merged_adjust.status_code == 409

    # 排课正式门禁只接受同学期、已终审 READY 的教学任务；merge survivor 也必须完成正式确认链。
    confirmed = client.post(f"{BASE}/teaching-tasks/{t1}/teacher-act", headers=teacher_hdr,
                            json={"action": "CONFIRM"})
    assert confirmed.status_code == 200, confirmed.text
    college = client.post(f"{BASE}/teaching-task-batches/{bid}/college-confirm", headers=college_hdr)
    assert college.status_code == 200, college.text
    reviewed = client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr,
                           json={"action": "APPROVE"})
    assert reviewed.status_code == 200, reviewed.text
    ready = {row["taskId"]: row for row in _tasks(client, hdr, bid)}[t1]
    assert ready["status"] == "READY"

    sb_resp = client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": str(tid)})
    assert sb_resp.status_code == 200, sb_resp.text
    sb = sb_resp.json()["data"]["batchId"]
    item = client.post(f"{BASE}/schedule-batches/{sb}/items", headers=hdr, json={
        "taskId": str(t1), "weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
        "teacherKey": "academic01", "teacherName": "赵敏", "classId": str(ids["class1"]),
        "className": "软件2601", "classroom": "A101", "courseName": "程序设计"})
    assert item.status_code == 200, item.text
    scheduled_adjust = client.post(f"{BASE}/teaching-tasks/{t1}/adjust", headers=college_hdr,
                                   json={"weeklyHours": 4, "reason": "已排课后尝试调整教学任务"})
    assert scheduled_adjust.status_code == 409
    stu = _hdr(client, "student01")
    forbidden = client.post(f"{BASE}/teaching-tasks/{t1}/adjust", headers=stu,
                            json={"weeklyHours": 4, "reason": "越权尝试调整教学任务"})
    assert forbidden.status_code == 403
