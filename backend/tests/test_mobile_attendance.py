"""波5 课堂考勤（移动端首创）端到端：新建场次(按行政班圈定名单)→标记→提交→范围收敛。"""
from __future__ import annotations

import json

BASE = "/api/v1/mobile/teacher/academic/attendance"
STUDENT_BASE = "/api/v1/mobile/academic"
MAIN = 1000000000000000001
DEMO = 1000000000000000003


def _teacher_token(real_name="王老师", tenant_id=MAIN, tid="demo", role="ACADEMIC_TEACHER"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "TEACHER",
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": "TEACHER_MINI"})}


def _seed_class(n_students=3, tenant_id=MAIN):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    try:
        c = SchoolClass(tenant_id=tenant_id, major_id=1, class_name="考勤测2601",
                        grade="2026", status="ACTIVE")
        db.add(c); db.flush()
        cid = c.id
        for i in range(n_students):
            db.add(StudentProfile(tenant_id=tenant_id, student_no=f"AT{i:04d}",
                                  real_name=f"考勤生{i}", class_id=cid,
                                  current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
        db.commit()
        return cid
    finally:
        db.close()


def _seed_teaching_task(class_id, teacher_key, tenant_id=MAIN):
    """建立可被正式 occurrence Authority 消费的完整教学任务/名单/课表事实。"""
    import hashlib
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse, AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead,
        AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion,
        AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch, AaTerm,
        StudentProfile,
    )
    db = get_sessionmaker()()
    try:
        # 2026-07-14/15 均落在第20教学周，weekday 分别为 2/3。
        term = AaTerm(
            tenant_id=tenant_id, year_code="2026-2027", term_no=1,
            term_name="2026-2027学年第一学期",
            start_date=datetime(2026, 3, 2), end_date=datetime(2026, 7, 19),
            teaching_weeks=20, is_current=True, status="PUBLISHED")
        db.add(term); db.flush()
        course = AaCourse(
            tenant_id=tenant_id,
            course_code=f"AT-C-{class_id}",
            course_name="测试课程",
            credit=2,
            status="ENABLED",
        )
        db.add(course); db.flush()
        batch = AaTeachingTaskBatch(
            tenant_id=tenant_id, term_id=term.id,
            batch_name="考勤测试教学任务批次", status="APPROVED")
        db.add(batch); db.flush()
        stable_teacher_key = f"u-{teacher_key}"
        task = AaTeachingTask(
            tenant_id=tenant_id, batch_id=batch.id, course_id=course.id,
            course_code=course.course_code, class_id=class_id,
            course_name=course.course_name, teacher_key=stable_teacher_key,
            teacher_name=teacher_key, status="READY",
            weekly_hours=2, total_hours=40, start_week=1, end_week=20)
        db.add(task); db.flush()

        student_ids = [
            int(value) for (value,) in db.query(StudentProfile.id).filter(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.class_id == int(class_id),
                StudentProfile.is_deleted.is_(False),
            ).order_by(StudentProfile.student_no, StudentProfile.id).all()
        ]
        assert student_ids, "考勤测试行政班必须存在学生"
        teaching_class = AaTeachingClass(
            tenant_id=tenant_id, teaching_task_id=task.id, term_id=term.id,
            course_id=task.course_id, class_code=f"TC-{term.id}-{task.id}",
            class_name=f"{task.course_name} · 考勤测试班", class_type="ADMIN",
            source_type="TEACHING_TASK", source_id=task.id,
            capacity=len(student_ids), current_roster_version_no=0,
            roster_status="DRAFT", status="ACTIVE", source_snapshot_json="{}")
        db.add(teaching_class); db.flush()
        digest = hashlib.sha256(
            ",".join(str(value) for value in sorted(set(student_ids))).encode("utf-8")
        ).hexdigest()
        version = AaTeachingClassRosterVersion(
            tenant_id=tenant_id, teaching_class_id=teaching_class.id,
            version_no=1, source_type="ADMIN_CLASS", source_id=int(class_id),
            member_count=len(student_ids), roster_hash=digest, status="LOCKED",
            reason="考勤合同测试正式名单", locked_at=datetime.utcnow(),
            locked_by=stable_teacher_key)
        db.add(version); db.flush()
        for student_id in student_ids:
            db.add(AaTeachingClassMember(
                tenant_id=tenant_id, teaching_class_id=teaching_class.id,
                roster_version_id=version.id, student_id=student_id,
                source_type="ADMIN_CLASS", source_id=int(class_id), status="ACTIVE"))
        db.add(AaTeachingClassTeacher(
            tenant_id=tenant_id, teaching_class_id=teaching_class.id,
            teacher_key=stable_teacher_key, teacher_name=teacher_key,
            role_type="PRIMARY", start_week=1, end_week=20, status="ACTIVE"))
        teaching_class.current_roster_version_id = version.id
        teaching_class.current_roster_version_no = 1
        teaching_class.roster_status = "LOCKED"
        task.expected_students = len(student_ids)

        # 旧测试此前只有 TeachingTask，没有 Published Schedule/ScopeHead。C-W1 后普通
        # 考勤必须命中当前正式课次，所以这里直接铺两条真实 EFFECTIVE 周二/周三课次。
        schedule_batch = AaScheduleBatch(
            tenant_id=tenant_id,
            term_id=term.id,
            batch_name="考勤测试正式课表",
            status="PUBLISHED",
        )
        db.add(schedule_batch); db.flush()
        for weekday in (2, 3):
            db.add(AaScheduleItem(
                tenant_id=tenant_id,
                batch_id=schedule_batch.id,
                task_id=task.id,
                course_id=course.id,
                course_name=course.course_name,
                teacher_key=stable_teacher_key,
                teacher_name=teacher_key,
                class_id=int(class_id),
                class_name="考勤测2601",
                weekday=weekday,
                slot_no=1,
                start_week=1,
                end_week=20,
                week_parity="ALL",
                classroom_text="AT-101",
                status="EFFECTIVE",
            ))
        db.flush()
        head = AaScheduleScopeHead(
            tenant_id=tenant_id,
            term_id=term.id,
            scope_type="SCHOOL",
            scope_id=0,
            active_batch_id=schedule_batch.id,
            version=1,
            published_at=datetime.utcnow(),
        )
        db.add(head)
        db.commit()
        return task.id
    finally:
        db.close()


def _student_header(real_name, student_no, tenant_id=MAIN, tid="demo"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "userType": "STUDENT",
        "studentNo": student_no, "tid": tid, "tenantId": str(tenant_id),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "STUDENT_MINI",
    })}


def _seed_attendance_pages():
    """建立只读学生考勤合同：历史行政班 + 当前已转班学生 + 坏/重复旧名单。"""
    from app.db.session import get_sessionmaker
    from app.models import AaAttendanceSession, SchoolClass, StudentProfile

    db = get_sessionmaker()()
    try:
        former_class = SchoolClass(
            tenant_id=MAIN, major_id=1, class_name="考勤历史班", grade="2025", status="ACTIVE",
        )
        current_class = SchoolClass(
            tenant_id=MAIN, major_id=1, class_name="考勤当前班", grade="2026", status="ACTIVE",
        )
        db.add_all([former_class, current_class])
        db.flush()
        # 甲现在已转到新班；本人历史考勤仍必须由提交名单而非当前 class_id 读取。
        student_a = StudentProfile(
            tenant_id=MAIN, student_no="ATPAGE-A", real_name="考勤分页甲", class_id=current_class.id,
            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
        )
        student_b = StudentProfile(
            tenant_id=MAIN, student_no="ATPAGE-B", real_name="考勤分页乙", class_id=current_class.id,
            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
        )
        student_c = StudentProfile(
            tenant_id=MAIN, student_no="ATPAGE-C", real_name="考勤分页丙", class_id=current_class.id,
            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
        )
        # 同学号放在另一学校，只用于确认 tenant 不能读到 MAIN 的场次。
        demo_student = StudentProfile(
            tenant_id=DEMO, student_no="ATPAGE-A", real_name="考勤分页甲",
            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
        )
        db.add_all([student_a, student_b, student_c, demo_student])
        db.flush()
        statuses = ["PRESENT"] * 5 + ["LATE"] * 4 + ["ABSENT"] * 4 + ["LEAVE"] * 4 + ["OTHER"] * 4
        for index, status in enumerate(statuses, start=1):
            roster = [
                {"studentId": str(student_a.id), "status": status},
                {"studentId": str(student_b.id), "status": "PRESENT"},
            ]
            if index == 1:
                # Legacy duplicate: first roster element remains authoritative.
                roster.insert(1, {"studentId": str(student_a.id), "status": "ABSENT"})
            db.add(AaAttendanceSession(
                tenant_id=MAIN, class_id=former_class.id,
                teaching_task_id=101 if index <= 11 else 202,
                course_name="电工基础" if index <= 11 else "语文基础",
                session_date=f"2026-09-{index:02d}", slot_no=1,
                roster_json=json.dumps(roster), status="SUBMITTED",
            ))
        # Bad historical JSON must not make the student page fail or expose a
        # class-wide governance counter.
        db.add(AaAttendanceSession(
            tenant_id=MAIN, class_id=former_class.id, teaching_task_id=101,
            course_name="电工基础", session_date="2026-09-30", slot_no=1,
            roster_json="{bad-json", status="SUBMITTED",
        ))
        # 另一学校存在同名学生与同类记录；MAIN 学生查询必须仍只得到上面的 21 条。
        db.add(AaAttendanceSession(
            tenant_id=DEMO, class_id=1, teaching_task_id=101,
            course_name="电工基础", session_date="2026-09-30", slot_no=1,
            roster_json=json.dumps([{"studentId": str(demo_student.id), "status": "PRESENT"}]),
            status="SUBMITTED",
        ))
        db.commit()
        return student_a.id, student_b.id, student_c.id, demo_student.id
    finally:
        db.close()


def test_attendance_full_flow(client, db_mode):
    cid = _seed_class(n_students=3)
    task_id = _seed_teaching_task(cid, "周老师")
    hdr = _teacher_token("周老师")
    r = client.post(f"{BASE}/sessions", headers=hdr,
                    json={"teachingTaskId": task_id, "classId": cid,
                          "courseName": "高等数学", "sessionDate": "2026-07-15",
                          "slotNo": 1}).json()
    assert r["code"] == 0, r
    sess = r["data"]
    assert sess["totalCount"] == 3 and sess["presentCount"] == 0 and sess["status"] == "DRAFT"
    sid = sess["sessionId"]

    detail = client.get(f"{BASE}/sessions/{sid}", headers=hdr).json()["data"]
    assert len(detail["items"]) == 3
    stu0 = detail["items"][0]
    assert all(row["status"] == "UNMARKED" for row in detail["items"])
    premature = client.post(f"{BASE}/sessions/{sid}/submit", headers=hdr)
    assert premature.status_code == 409
    assert premature.json()["details"]["unmarkedCount"] == 3

    marked = client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr,
                         json={"studentId": stu0["studentId"], "status": "ABSENT"}).json()["data"]
    assert marked["absentCount"] == 1 and marked["presentCount"] == 0
    partial = client.post(f"{BASE}/sessions/{sid}/submit", headers=hdr)
    assert partial.status_code == 409
    assert client.get(f"{BASE}/sessions/{sid}", headers=hdr).json()["data"]["status"] == "DRAFT"
    for student in detail["items"][1:]:
        response = client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr,
                               json={"studentId": student["studentId"], "status": "PRESENT"})
        assert response.status_code == 200

    submitted = client.post(f"{BASE}/sessions/{sid}/submit", headers=hdr).json()["data"]
    assert submitted["status"] == "SUBMITTED"
    assert submitted["presentCount"] == 2 and submitted["absentCount"] == 1
    assert submitted["warningScanOk"] is True

    # 提交后不可再改
    blocked = client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr,
                          json={"studentId": stu0["studentId"], "status": "PRESENT"}).json()
    assert blocked["code"] != 0

    # 列表里能看到本人这条场次
    lst = client.get(f"{BASE}/sessions", headers=hdr).json()["data"]
    assert lst["total"] >= 1
    assert any(s["sessionId"] == sid for s in lst["items"])


def test_attendance_submit_keeps_committed_result_honest_when_warning_scan_fails(client, db_mode, monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_warning_service as warning

    cid = _seed_class(n_students=1)
    task_id = _seed_teaching_task(cid, "预警回执老师")
    hdr = _teacher_token("预警回执老师")
    created = client.post(f"{BASE}/sessions", headers=hdr, json={
        "teachingTaskId": task_id, "classId": cid, "sessionDate": "2026-07-15", "slotNo": 1,
    }).json()["data"]
    sid = created["sessionId"]
    detail = client.get(f"{BASE}/sessions/{sid}", headers=hdr).json()["data"]
    assert client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr, json={
        "studentId": detail["items"][0]["studentId"], "status": "PRESENT",
    }).status_code == 200
    monkeypatch.setattr(warning, "scan_attendance_warnings", lambda _user: (_ for _ in ()).throw(RuntimeError("scan offline")))
    response = client.post(f"{BASE}/sessions/{sid}/submit", headers=hdr)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "SUBMITTED"
    assert result["warningScanOk"] is False
    assert "扫描未完成" in result["warningScanError"]


def test_attendance_other_teacher_cannot_view_or_mark(client, db_mode):
    """teacher_key 归属收敛：非本人创建的场次，另一教师应被拦截。"""
    cid = _seed_class(n_students=2)
    task_id = _seed_teaching_task(cid, "张老师")
    owner_hdr = _teacher_token("张老师")
    r = client.post(f"{BASE}/sessions", headers=owner_hdr,
                    json={"teachingTaskId": task_id, "classId": cid,
                          "courseName": "英语", "sessionDate": "2026-07-15",
                          "slotNo": 1}).json()
    assert r["code"] == 0, r
    sid = r["data"]["sessionId"]

    other_hdr = _teacher_token("李老师")
    blocked = client.get(f"{BASE}/sessions/{sid}", headers=other_hdr).json()
    assert blocked["code"] != 0

    # 另一教师自己的场次列表里也不应该出现这条
    other_list = client.get(f"{BASE}/sessions", headers=other_hdr).json()["data"]
    assert not any(s["sessionId"] == sid for s in other_list["items"])


def test_teacher_attendance_sessions_and_roster_are_server_paged(client, db_mode):
    """教师端不能把场次或 65 人名单一次性下发给小程序。

    这条回归同时验证当前页之外仍由服务端完整状态机守住：只标第三页
    一人以后提交仍会被 64 名未点名学生阻止。
    """
    from app.db.session import get_sessionmaker
    from app.models import AaAttendanceSession

    cid = _seed_class(n_students=65)
    task_id = _seed_teaching_task(cid, "分页老师")
    hdr = _teacher_token("分页老师")
    created = client.post(f"{BASE}/sessions", headers=hdr, json={
        "teachingTaskId": task_id, "classId": cid,
        "sessionDate": "2026-07-15", "slotNo": 1,
    })
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["sessionId"]

    # 旧场次没有正式快照时仍按稳定教师工号授权；它们用于验证列表确实是
    # 服务端 20 条一页，而不是小程序对本地 50 条切片。
    db = get_sessionmaker()()
    try:
        db.add_all([
            AaAttendanceSession(
                tenant_id=MAIN, class_id=cid, teacher_key="u-分页老师",
                course_name="历史分页考勤", session_date=f"2026-08-{index:02d}",
                slot_no=1, roster_json=json.dumps([]), total_count=0, status="DRAFT",
            )
            for index in range(1, 21)
        ])
        db.commit()
    finally:
        db.close()

    sessions_first = client.get(f"{BASE}/sessions", headers=hdr, params={"page": 1, "pageSize": 20})
    assert sessions_first.status_code == 200, sessions_first.text
    first_data = sessions_first.json()["data"]
    assert first_data["total"] == 21 and first_data["page"] == 1 and first_data["pageSize"] == 20
    assert len(first_data["items"]) == 20 and first_data["hasMore"] is True
    sessions_second = client.get(f"{BASE}/sessions", headers=hdr, params={"page": 2, "pageSize": 20})
    second_data = sessions_second.json()["data"]
    assert len(second_data["items"]) == 1 and second_data["hasMore"] is False
    assert {row["sessionId"] for row in first_data["items"]}.isdisjoint(
        {row["sessionId"] for row in second_data["items"]}
    )

    pages = [
        client.get(f"{BASE}/sessions/{sid}", headers=hdr, params={"page": page, "pageSize": 30})
        for page in (1, 2, 3)
    ]
    assert all(response.status_code == 200 for response in pages)
    details = [response.json()["data"] for response in pages]
    assert [len(detail["items"]) for detail in details] == [30, 30, 5]
    assert all(detail["total"] == 65 and detail["totalCount"] == 65 for detail in details)
    assert details[0]["hasMore"] is True and details[1]["hasMore"] is True and details[2]["hasMore"] is False
    assert details[0]["summary"] == {"PRESENT": 0, "LATE": 0, "ABSENT": 0, "LEAVE": 0, "UNMARKED": 65}
    assert details[0]["rosterIntegrity"] == "READY"
    seen = [row["studentId"] for detail in details for row in detail["items"]]
    assert len(seen) == 65 and len(set(seen)) == 65

    third_page_student = details[2]["items"][0]
    mark = client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr, json={
        "studentId": third_page_student["studentId"], "status": "LATE",
    })
    assert mark.status_code == 200, mark.text
    receipt = mark.json()["data"]
    assert "items" not in receipt
    assert receipt["item"]["studentId"] == third_page_student["studentId"]
    assert receipt["summary"]["LATE"] == 1 and receipt["unmarkedCount"] == 64

    reread = client.get(f"{BASE}/sessions/{sid}", headers=hdr, params={"page": 1, "pageSize": 30}).json()["data"]
    assert reread["summary"]["LATE"] == 1 and reread["unmarkedCount"] == 64
    blocked = client.post(f"{BASE}/sessions/{sid}/submit", headers=hdr)
    assert blocked.status_code == 409
    assert blocked.json()["details"]["unmarkedCount"] == 64

    other = _teacher_token("无权分页老师")
    assert client.get(f"{BASE}/sessions/{sid}", headers=other).status_code == 403
    # This project maps FastAPI validation errors to its Chinese 400 envelope;
    # the important boundary is that malformed URL ids never reach int() and 500.
    assert client.get(f"{BASE}/sessions/not-a-number", headers=hdr).status_code == 400
    assert client.post(f"{BASE}/sessions/not-a-number/mark", headers=hdr, json={}).status_code == 400
    assert client.post(f"{BASE}/sessions/not-a-number/submit", headers=hdr).status_code == 400


def test_attendance_empty_class_not_found(client, db_mode):
    """行政班无学生名单：明确报错，不 500、不建空场次。"""
    hdr = _teacher_token("赵老师")
    r = client.post(f"{BASE}/sessions", headers=hdr,
                    json={"classId": 999999999, "courseName": "无人班", "sessionDate": "2026-07-15"}).json()
    assert r["code"] != 0


def test_attendance_requires_login(client):
    assert client.get(f"{BASE}/sessions").json()["code"] == 401001


def _hdr_admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_attendance_pc_stats_and_type(client, db_mode):
    """PC 跨堂次统计(正方4.19)+点名类别：教师建2场次点名提交，教务处按学生汇总旷课并可按类别过滤。"""
    cid = _seed_class(n_students=3)
    task_id = _seed_teaching_task(cid, "孙老师")
    hdr = _teacher_token("孙老师")
    PC = "/api/v1/academic-affairs/attendance"
    # 场次1：常规类别（不传=常规），1 人旷课
    s1_payload = client.post(f"{BASE}/sessions", headers=hdr, json={
        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",
        "termCode": "2026-1", "sessionDate": "2026-07-14", "slotNo": 1}).json()
    assert s1_payload["code"] == 0, s1_payload
    s1 = s1_payload["data"]
    absent_sid = client.get(f"{BASE}/sessions/{s1['sessionId']}", headers=hdr).json()["data"]["items"][0]["studentId"]
    client.post(f"{BASE}/sessions/{s1['sessionId']}/mark", headers=hdr,
                json={"studentId": absent_sid, "status": "ABSENT"})
    for student in client.get(f"{BASE}/sessions/{s1['sessionId']}", headers=hdr).json()["data"]["items"]:
        if student["studentId"] != absent_sid:
            client.post(f"{BASE}/sessions/{s1['sessionId']}/mark", headers=hdr,
                        json={"studentId": student["studentId"], "status": "PRESENT"})
    assert client.post(f"{BASE}/sessions/{s1['sessionId']}/submit", headers=hdr).status_code == 200
    # 场次2：实训类别，同一人再旷课
    s2_payload = client.post(f"{BASE}/sessions", headers=hdr, json={
        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",
        "termCode": "2026-1", "sessionDate": "2026-07-15", "slotNo": 1,
        "sessionType": "实训"}).json()
    assert s2_payload["code"] == 0, s2_payload
    s2 = s2_payload["data"]
    assert s2["sessionType"] == "实训"
    client.post(f"{BASE}/sessions/{s2['sessionId']}/mark", headers=hdr,
                json={"studentId": absent_sid, "status": "ABSENT"})
    for student in client.get(f"{BASE}/sessions/{s2['sessionId']}", headers=hdr).json()["data"]["items"]:
        if student["studentId"] != absent_sid:
            client.post(f"{BASE}/sessions/{s2['sessionId']}/mark", headers=hdr,
                        json={"studentId": student["studentId"], "status": "PRESENT"})
    assert client.post(f"{BASE}/sessions/{s2['sessionId']}/submit", headers=hdr).status_code == 200

    admin = _hdr_admin(client)
    stats = client.get(f"{PC}/stats", headers=admin, params={"classId": cid}).json()["data"]
    assert stats["sessionCount"] == 2
    top = stats["students"][0]  # 按旷课次数降序
    assert top["studentId"] == absent_sid and top["absent"] == 2 and top["sessions"] == 2
    paged = client.get(
        f"{PC}/stats", headers=admin,
        params={"classId": cid, "page": 1, "pageSize": 1},
    ).json()["data"]
    assert paged["studentTotal"] == len(stats["students"])
    assert paged["absentStudentCount"] == 1
    assert paged["page"] == 1 and paged["pageSize"] == 1
    assert len(paged["students"]) == 1 and paged["students"][0]["studentId"] == absent_sid
    # 点名类别过滤：只看实训 → 该生旷课 1、场次 1
    only = client.get(f"{PC}/stats", headers=admin, params={"classId": cid, "sessionType": "实训"}).json()["data"]
    assert only["sessionCount"] == 1 and only["students"][0]["absent"] == 1
    # PC 场次列表可查
    lst = client.get(f"{PC}/sessions", headers=admin, params={"classId": cid}).json()["data"]
    assert lst["total"] == 2


def test_mobile_attendance_is_server_paged_course_filtered_and_self_scoped(client, db_mode):
    student_a_id, _student_b_id, _student_c_id, other_school_student_id = _seed_attendance_pages()
    student_a = _student_header("考勤分页甲", "ATPAGE-A")

    first_response = client.get(f"{STUDENT_BASE}/attendance/my", headers=student_a, params={
        "page": 1, "pageSize": 20,
    })
    assert first_response.status_code == 200, first_response.text
    first = first_response.json()["data"]
    assert len(first["items"]) == 20
    assert first["total"] == 21 and first["page"] == 1 and first["pageSize"] == 20 and first["hasMore"] is True
    assert first["summary"] == {"PRESENT": 5, "LATE": 4, "ABSENT": 4, "LEAVE": 4, "OTHER": 4}
    assert all("studentId" not in row and "realName" not in row and "roster" not in row for row in first["items"])

    second_response = client.get(f"{STUDENT_BASE}/attendance/my", headers=student_a, params={
        "page": 2, "pageSize": 20,
    })
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()["data"]
    assert len(second["items"]) == 1 and second["hasMore"] is False
    assert {row["sessionId"] for row in first["items"]}.isdisjoint({row["sessionId"] for row in second["items"]})

    filtered_response = client.get(f"{STUDENT_BASE}/attendance/my", headers=student_a, params={
        "course": "电工", "page": 1, "pageSize": 20,
    })
    assert filtered_response.status_code == 200, filtered_response.text
    filtered = filtered_response.json()["data"]
    assert filtered["total"] == 11 and len(filtered["items"]) == 11
    assert all("电工" in row["courseName"] for row in filtered["items"])

    # 同名课程不靠模糊名称混合：从正式课表深链携带的教学任务 ID 是精确边界。
    task_filtered = client.get(f"{STUDENT_BASE}/attendance/my", headers=student_a, params={
        "course": "电工", "teachingTaskId": 101, "page": 1, "pageSize": 20,
    })
    assert task_filtered.status_code == 200, task_filtered.text
    assert task_filtered.json()["data"]["total"] == 11

    # Student C is in the same administrative class but never appears in a roster.
    # A forged query studentId must not replace the token-derived student binding.
    student_c = client.get(f"{STUDENT_BASE}/attendance/my", headers=_student_header("考勤分页丙", "ATPAGE-C"), params={
        "studentId": str(student_a_id), "page": 1, "pageSize": 20,
    })
    assert student_c.status_code == 200, student_c.text
    result_c = student_c.json()["data"]
    assert result_c["items"] == [] and result_c["total"] == 0

    # The API only exposes the caller's status projection, not the other roster member.
    student_b = client.get(f"{STUDENT_BASE}/attendance/my", headers=_student_header("考勤分页乙", "ATPAGE-B"))
    assert student_b.status_code == 200, student_b.text
    assert student_b.json()["data"]["summary"]["PRESENT"] == 21

    # Another school has a same-number student and one submitted session.  A URL
    # parameter cannot replace the token tenant or make that row appear here.
    cross_school = client.get(f"{STUDENT_BASE}/attendance/my", headers=student_a, params={
        "studentId": str(other_school_student_id), "page": 1, "pageSize": 100,
    })
    assert cross_school.status_code == 200, cross_school.text
    assert cross_school.json()["data"]["total"] == 21

    teacher = client.get(f"{STUDENT_BASE}/attendance/my", headers=_teacher_token("越权教师"))
    assert teacher.status_code == 403
