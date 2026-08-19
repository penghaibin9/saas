"""波5 课堂考勤（移动端首创）端到端：新建场次(按行政班圈定名单)→标记→提交→范围收敛。"""
from __future__ import annotations

BASE = "/api/v1/mobile/teacher/academic/attendance"
MAIN = 1000000000000000001
DEMO = 1000000000000000003


def _teacher_token(real_name="王老师", tenant_id=MAIN, tid="demo", role="ACADEMIC_TEACHER"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "TEACHER",
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": "MP"})}


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
    assert sess["totalCount"] == 3 and sess["presentCount"] == 3 and sess["status"] == "DRAFT"
    sid = sess["sessionId"]

    detail = client.get(f"{BASE}/sessions/{sid}", headers=hdr).json()["data"]
    assert len(detail["items"]) == 3
    stu0 = detail["items"][0]
    assert stu0["status"] == "PRESENT"

    marked = client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr,
                         json={"studentId": stu0["studentId"], "status": "ABSENT"}).json()["data"]
    assert marked["absentCount"] == 1 and marked["presentCount"] == 2

    submitted = client.post(f"{BASE}/sessions/{sid}/submit", headers=hdr).json()["data"]
    assert submitted["status"] == "SUBMITTED"

    # 提交后不可再改
    blocked = client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr,
                          json={"studentId": stu0["studentId"], "status": "PRESENT"}).json()
    assert blocked["code"] != 0

    # 列表里能看到本人这条场次
    lst = client.get(f"{BASE}/sessions", headers=hdr).json()["data"]
    assert lst["total"] >= 1
    assert any(s["sessionId"] == sid for s in lst["items"])


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
    client.post(f"{BASE}/sessions/{s1['sessionId']}/submit", headers=hdr)
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
    client.post(f"{BASE}/sessions/{s2['sessionId']}/submit", headers=hdr)

    admin = _hdr_admin(client)
    stats = client.get(f"{PC}/stats", headers=admin, params={"classId": cid}).json()["data"]
    assert stats["sessionCount"] == 2
    top = stats["students"][0]  # 按旷课次数降序
    assert top["studentId"] == absent_sid and top["absent"] == 2 and top["sessions"] == 2
    # 点名类别过滤：只看实训 → 该生旷课 1、场次 1
    only = client.get(f"{PC}/stats", headers=admin, params={"classId": cid, "sessionType": "实训"}).json()["data"]
    assert only["sessionCount"] == 1 and only["students"][0]["absent"] == 1
    # PC 场次列表可查
    lst = client.get(f"{PC}/sessions", headers=admin, params={"classId": cid}).json()["data"]
    assert lst["total"] == 2