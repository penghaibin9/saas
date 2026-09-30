"""13B-P7 多端收口 · 端到端（教务学生自视图 + 教师课表）。

MB1 我的课表；MB2 我的成绩单；MB3 我的学籍+异动申请(本人)；MB4 我的毕业进度；
MB5 教师我的课表；MB6 非学生调自视图403。
"""
from __future__ import annotations

TID = 1000000000000000001
AA = "/api/v1/academic-affairs"
MB = "/api/v1/mobile"


def _hdr(client, login_name, client_type="PC"):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any", "clientType": client_type}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no, student_id=None):
    from app.core.security import create_access_token
    claims = {
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        # 正式学生小程序登录只签发 STUDENT_MINI。旧泛 MP 令牌应由
        # require_mobile_student 拒绝，不能再用于把移动端课表回归伪装成通过。
        "currentRoleCode": "STUDENT", "clientType": "STUDENT_MINI"}
    if student_id is not None:
        claims["studentId"] = str(student_id)
    return {"Authorization": "Bearer " + create_access_token(claims)}


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


def _seed_ready_task(term_id, class_id, teacher_key, weekly_hours=1):
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
        weekly_hours=int(weekly_hours), total_hours=int(weekly_hours) * 18, start_week=1, end_week=18,
    )
    db.add(task); db.flush()
    task_id = int(task.id)
    db.commit()
    db.close()
    return task_id


def _published_schedule(client, admin, class_id, teacher_key="counselor01", extra_items=None):
    term_id = _ensure_term()
    task_id = _seed_ready_task(term_id, class_id, teacher_key, weekly_hours=1 + len(extra_items or []))
    # 发布课表必须落到正式教室字典；不能只传展示文本 A101。
    classroom = client.post(f"{AA}/classrooms", headers=admin, json={
        "buildingCode": "MB", "buildingName": "移动端教学楼",
        "roomCode": str(class_id), "capacity": 60, "roomType": "MULTIMEDIA",
    })
    assert classroom.status_code == 200, classroom.text
    classroom_name = classroom.json()["data"]["roomName"]
    created = client.post(f"{AA}/schedule-batches", headers=admin, json={"termId": str(term_id)})
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]
    item = client.post(f"{AA}/schedule-batches/{bid}/items", headers=admin, json={
        "taskId": str(task_id),
        "weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
        "teacherKey": teacher_key, "teacherName": "王老师",
        "classId": str(class_id), "className": "软件2301", "classroom": classroom_name, "courseName": "高数"})
    assert item.status_code == 200, item.text
    for extra in extra_items or []:
        response = client.post(f"{AA}/schedule-batches/{bid}/items", headers=admin, json={
            "taskId": str(task_id),
            "weekday": 2, "slotNo": 2, "startWeek": 2, "endWeek": 2, "weekParity": "ALL",
            "teacherKey": teacher_key, "teacherName": "王老师",
            "classId": str(class_id), "className": "软件2301", "classroom": classroom_name,
            "courseName": "高数",
            **extra,
        })
        assert response.status_code == 200, response.text
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
    assert r["data"]["week"] == 1


def test_mobile_schedule_reads_one_server_filtered_teaching_week(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _published_schedule(client, admin, ids["class"], extra_items=[{}])
    student = _stu_token("移动甲", "AAM01")

    first = client.get(f"{MB}/academic/schedule/my?week=1", headers=student)
    second = client.get(f"{MB}/academic/schedule/my?week=2", headers=student)
    teacher_first = client.get(
        f"{MB}/academic/teacher-schedule/my?week=1",
        headers=_hdr(client, "counselor01", "TEACHER_MINI"),
    )
    teacher_second = client.get(
        f"{MB}/academic/teacher-schedule/my?week=2",
        headers=_hdr(client, "counselor01", "TEACHER_MINI"),
    )

    assert first.status_code == second.status_code == teacher_first.status_code == teacher_second.status_code == 200
    assert first.json()["data"]["week"] == teacher_first.json()["data"]["week"] == 1
    assert second.json()["data"]["week"] == teacher_second.json()["data"]["week"] == 2
    assert len(first.json()["data"]["items"]) == len(teacher_first.json()["data"]["items"]) == 1
    assert len(second.json()["data"]["items"]) == len(teacher_second.json()["data"]["items"]) == 2
    assert all(int(item["startWeek"]) <= 1 <= int(item["endWeek"]) for item in first.json()["data"]["items"])
    assert all(int(item["startWeek"]) <= 2 <= int(item["endWeek"]) for item in second.json()["data"]["items"])


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
    evidence = client.get(f"{AA}/grade-tasks/{tid}/review-evidence", headers=admin)
    assert evidence.status_code == 200, evidence.text
    reviewed = client.post(f"{AA}/grade-tasks/{tid}/college-review", headers=admin,
                           json={"action": "APPROVE", "expectedEvidenceHash": evidence.json()["data"]["evidenceHash"]})
    assert reviewed.status_code == 200, reviewed.text
    published = client.post(f"{AA}/grade-tasks/{tid}/publish", headers=admin)
    assert published.status_code == 200, published.text
    r = client.get(f"{MB}/academic/transcript/my?page=1&pageSize=20", headers=_stu_token("移动甲", "AAM01")).json()
    assert any(g["courseName"] == "高数" for g in r["data"]["items"])
    assert r["data"]["page"] == 1 and r["data"]["pageSize"] == 20
    assert r["data"]["hasMore"] is False


def test_mobile_academic_read_lists_expose_bounded_page_contracts(client, db_mode):
    _seed(db_mode)
    student = _stu_token("移动甲", "AAM01")
    transcript = client.get(f"{MB}/academic/transcript/my?page=1&pageSize=20", headers=student)
    credits = client.get(f"{MB}/academic/credits/my?page=1&pageSize=20", headers=student)
    exams = client.get(f"{MB}/academic/exam/my?page=1&pageSize=20", headers=student)

    assert transcript.status_code == credits.status_code == exams.status_code == 200
    for payload, items_key, total_key in (
        (transcript.json()["data"], "items", "total"),
        (credits.json()["data"], "passedCourses", "passedCoursesTotal"),
        (exams.json()["data"], "items", "total"),
    ):
        assert payload["page"] == 1 and payload["pageSize"] == 20
        assert isinstance(payload[items_key], list)
        assert isinstance(payload[total_key], int) and payload[total_key] >= len(payload[items_key])
        assert payload["hasMore"] is (payload["page"] * payload["pageSize"] < payload[total_key])


def test_mobile_defer_history_and_resubmit_use_stable_student_id_not_student_number(client, db_mode):
    """学号更正/伪造学号都不能改变缓考记录的本人归属。"""
    ids = _seed(db_mode)
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import AaDeferredExam, StudentProfile

    db = get_sessionmaker()()
    owner = db.get(StudentProfile, ids["student"])
    owner.student_no = "AAM01-CORRECTED"  # 历史业务快照仍保留原学号。
    other = StudentProfile(
        tenant_id=TID, student_no="AAM02", real_name="移动乙", grade="2023",
        student_status="REGISTERED", status="ACTIVE",
    )
    db.add(other)
    db.flush()
    deferred = AaDeferredExam(
        tenant_id=TID, student_id=owner.id, student_no="AAM01", student_name=owner.real_name,
        exam_course_id=999999, course_name="稳定身份缓考回归", reason_type="SICK",
        reason="学号更正后仍应由本人处理", apply_at=datetime.utcnow(),
        current_node="STUDENT", status="RETURNED", return_reason="请补充材料",
    )
    db.add(deferred)
    db.flush()
    defer_id = int(deferred.id)
    other_id = int(other.id)
    db.commit()
    db.close()

    owner_token = _stu_token("移动甲", "AAM01-CORRECTED", ids["student"])
    # ``studentNo`` is deliberately forged here.  The stable signed studentId must
    # win and keep this request inside B's own (empty) data scope.
    other_token = _stu_token("移动乙", "AAM01-CORRECTED", other_id)

    owner_rows = client.get(f"{MB}/academic/exam/defer/my?page=1&pageSize=20", headers=owner_token)
    assert owner_rows.status_code == 200, owner_rows.text
    owner_data = owner_rows.json()["data"]
    assert owner_data["page"] == 1 and owner_data["pageSize"] == 20
    assert owner_data["total"] == 1 and owner_data["hasMore"] is False
    assert [row["deferId"] for row in owner_data["items"]] == [str(defer_id)]

    other_rows = client.get(f"{MB}/academic/exam/defer/my?page=1&pageSize=20", headers=other_token)
    assert other_rows.status_code == 200, other_rows.text
    assert other_rows.json()["data"]["items"] == []
    assert client.post(f"{MB}/academic/exam/defer/{defer_id}/resubmit", headers=other_token).status_code == 403

    # A teacher cannot invoke the student-private history route by changing URL.
    assert client.get(f"{MB}/academic/exam/defer/my?page=1&pageSize=20", headers=_hdr(client, "counselor01")).status_code == 403
    assert client.post(f"{MB}/academic/exam/defer/{defer_id}/resubmit", headers=owner_token).status_code == 200


def test_mobile_defer_exact_link_finds_old_record_without_cross_student_or_school_access(client, db_mode):
    ids = _seed(db_mode)
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import AaDeferredExam, StudentProfile

    with get_sessionmaker()() as db:
        other = StudentProfile(tenant_id=TID, student_no="AAM-EXACT-B", real_name="精确定位乙", grade="2023", student_status="REGISTERED", status="ACTIVE")
        db.add(other)
        db.flush()
        other_id = int(other.id)
        row_ids = []
        for index in range(22):
            row = AaDeferredExam(tenant_id=TID, student_id=ids["student"], student_no="AAM01", student_name="移动甲",
                                 exam_course_id=990000 + index, course_name=f"缓考定位回归{index}", reason_type="SICK",
                                 reason="独立测试记录", apply_at=datetime.utcnow(), current_node="STUDENT", status="RETURNED")
            db.add(row)
            db.flush()
            row_ids.append(int(row.id))
        foreign = AaDeferredExam(tenant_id=TID + 1, student_id=ids["student"], student_no="AAM01", student_name="异校测试",
                                 exam_course_id=991000, course_name="跨校不可见", reason_type="SICK", reason="隔离测试",
                                 apply_at=datetime.utcnow(), current_node="STUDENT", status="RETURNED")
        db.add(foreign)
        db.flush()
        foreign_id = int(foreign.id)
        db.commit()

    owner_token = _stu_token("移动甲", "AAM01", ids["student"])
    first = client.get(f"{MB}/academic/exam/defer/my?page=1&pageSize=20", headers=owner_token)
    assert first.status_code == 200
    assert first.json()["data"]["total"] == 22
    assert str(row_ids[0]) not in [r["deferId"] for r in first.json()["data"]["items"]]
    exact = client.get(f"{MB}/academic/exam/defer/my?deferId={row_ids[0]}&page=1&pageSize=20", headers=owner_token)
    assert exact.status_code == 200
    assert exact.json()["data"]["total"] == 1
    assert [r["deferId"] for r in exact.json()["data"]["items"]] == [str(row_ids[0])]
    assert exact.json()["data"]["hasMore"] is False
    other_token = _stu_token("精确定位乙", "AAM01", other_id)
    for record_id, token in [(row_ids[0], other_token), (foreign_id, owner_token), (999999999999999999, owner_token)]:
        denied = client.get(f"{MB}/academic/exam/defer/my?deferId={record_id}", headers=token)
        assert denied.status_code == 404
        assert denied.json()["data"] is None
    assert client.get(f"{MB}/academic/exam/defer/my?deferId={row_ids[0]}", headers=_hdr(client, "counselor01")).status_code == 403


def test_mobile_recheck_history_is_paged_and_exact_grade_link_stays_self_scoped(client, db_mode):
    """复查历史不能全量下发；成绩单第 N 页的精确深链也不能越权。"""
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import AaGradeRecheck, AcademicGrade, AcademicStudent, StudentProfile

    db = get_sessionmaker()()
    owner = db.get(StudentProfile, ids["student"])
    academic = AcademicStudent(
        tenant_id=TID,
        student_id=owner.id,
        student_no=owner.student_no,
        name=owner.real_name,
        class_id=str(owner.class_id or ""),
        class_name="软件2301",
    )
    db.add(academic)
    db.flush()
    grade = AcademicGrade(
        tenant_id=TID,
        acad_student_id=academic.id,
        course_name="分页深链成绩",
        term="2026-1",
        credit_value=2,
        score=82,
        pass_status="PASSED",
        record_status="ACTIVE",
    )
    db.add(grade)
    db.flush()
    for index in range(21):
        db.add(AaGradeRecheck(
            tenant_id=TID,
            student_id=owner.id,
            student_no=owner.student_no,
            student_name=owner.real_name,
            acad_grade_id=grade.id,
            course_name=f"复查历史{index}",
            term="2026-1",
            original_score=80,
            reason="用于分页回归的复查记录",
            status="UPHELD",
        ))
    other = StudentProfile(
        tenant_id=TID,
        student_no="AAM03",
        real_name="移动丙",
        grade="2023",
        student_status="REGISTERED",
        status="ACTIVE",
    )
    db.add(other)
    db.flush()
    db.commit()
    db.close()

    owner_token = _stu_token("移动甲", "AAM01", ids["student"])
    second = client.get(f"{MB}/academic/grade-recheck/my?page=2&pageSize=20", headers=owner_token)
    assert second.status_code == 200, second.text
    second_data = second.json()["data"]
    assert second_data["page"] == 2 and second_data["pageSize"] == 20
    assert second_data["total"] == 21 and second_data["hasMore"] is False
    assert len(second_data["items"]) == 1

    exact = client.get(f"{MB}/academic/grade-recheck/eligible/{grade.id}", headers=owner_token)
    assert exact.status_code == 200, exact.text
    assert exact.json()["data"]["gradeId"] == str(grade.id)
    assert exact.json()["data"]["courseName"] == "分页深链成绩"

    other_token = _stu_token("移动丙", "AAM03", other.id)
    assert client.get(f"{MB}/academic/grade-recheck/eligible/{grade.id}", headers=other_token).status_code == 403
    assert client.get(f"{MB}/academic/grade-recheck/eligible/{grade.id}", headers=_hdr(client, "counselor01")).status_code == 403


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


def test_mobile_status_history_is_server_paged_and_isolated(client, db_mode):
    """异动历史只能读取本人的当前页；退回单仍带原单的重交版本。"""
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import AaStatusChange, StudentProfile

    db = get_sessionmaker()()
    other = StudentProfile(
        tenant_id=TID, student_no="AAM02", real_name="移动乙",
        college_id=ids["college"], major_id=ids["major"], class_id=ids["class"], grade="2023",
        current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE",
    )
    db.add(other)
    db.flush()
    for index in range(42):
        db.add(AaStatusChange(
            tenant_id=TID,
            student_id=ids["student"],
            change_type="SUSPEND",
            from_status="REGISTERED",
            to_status="SUSPENDED",
            reason=f"本人异动分页记录 {index:02d}",
            status="RETURNED" if index == 41 else "SUBMITTED",
            current_node="STUDENT" if index == 41 else "COUNSELOR",
            version=7 if index == 41 else 1,
            decision_version=3 if index == 41 else 0,
        ))
    db.add(AaStatusChange(
        tenant_id=TID,
        student_id=other.id,
        change_type="SUSPEND",
        from_status="REGISTERED",
        to_status="SUSPENDED",
        reason="另一名学生的异动记录",
        status="SUBMITTED",
        current_node="COUNSELOR",
    ))
    db.commit()
    db.close()

    owner = _stu_token("移动甲", "AAM01", ids["student"])
    pages = [
        client.get(f"{MB}/academic/status/my?page={page}&pageSize=20", headers=owner)
        for page in (1, 2, 3)
    ]
    assert all(response.status_code == 200 for response in pages), [response.text for response in pages]
    data = [response.json()["data"] for response in pages]
    assert [(item["page"], item["pageSize"], item["total"], item["hasMore"], len(item["changes"])) for item in data] == [
        (1, 20, 42, True, 20),
        (2, 20, 42, True, 20),
        (3, 20, 42, False, 2),
    ]
    ids_by_page = [{row["changeId"] for row in item["changes"]} for item in data]
    assert ids_by_page[0].isdisjoint(ids_by_page[1])
    assert ids_by_page[0].isdisjoint(ids_by_page[2])
    assert ids_by_page[1].isdisjoint(ids_by_page[2])
    returned = next(row for row in data[0]["changes"] if row["status"] == "RETURNED")
    assert returned["reason"] == "本人异动分页记录 41"
    assert returned["version"] == 7 and returned["decisionVersion"] == 3

    other_data = client.get(
        f"{MB}/academic/status/my?page=1&pageSize=20",
        headers=_stu_token("移动乙", "AAM02", other.id),
    ).json()["data"]
    assert other_data["total"] == 1
    assert other_data["changes"][0]["reason"] == "另一名学生的异动记录"


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
    r = client.get(
        f"{MB}/academic/teacher-schedule/my",
        headers=_hdr(client, "counselor01", "TEACHER_MINI"),
    ).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 1


def test_teacher_academic_mobile_routes_require_mini_identity_and_permission(client, db_mode):
    del db_mode
    endpoints = [
        ("GET", f"{MB}/academic/teacher-schedule/my"),
        ("GET", f"{MB}/teacher/academic/attendance/class-options"),
        ("GET", f"{MB}/teacher/academic/attendance/sessions"),
        ("POST", f"{MB}/teacher/academic/attendance/sessions"),
        ("GET", f"{MB}/teacher/academic/attendance/sessions/1"),
        ("POST", f"{MB}/teacher/academic/attendance/sessions/1/mark"),
        ("POST", f"{MB}/teacher/academic/attendance/sessions/1/submit"),
    ]
    pc_teacher = _hdr(client, "academic01")
    for method, url in endpoints:
        response = client.request(method, url, headers=pc_teacher, json={} if method == "POST" else None)
        assert response.status_code == 403, (method, url, response.text)

    # 就业教师是有效教师小程序身份，但没有教务课表/考勤权限；不能以“教师”统称越权。
    no_academic_permission = _hdr(client, "employment01", "TEACHER_MINI")
    for method, url in endpoints:
        response = client.request(method, url, headers=no_academic_permission, json={} if method == "POST" else None)
        assert response.status_code == 403, (method, url, response.text)


def test_mb6_non_student_403(client, db_mode):
    _seed(db_mode)
    r = client.get(f"{MB}/academic/schedule/my", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403
