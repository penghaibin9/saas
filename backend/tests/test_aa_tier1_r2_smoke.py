"""教务中心 Tier1-R2 补充烟雾测试。

本文件只锁四条高频链：学籍详情、成绩导入确认、正式教学任务课表、教学评价角色任务。
所有成绩/课表夹具统一使用真实学期、稳定课程版本、READY 教学任务与启用节次，
不再依赖 free-text courseName、伪 course_id 或绕过生产身份门禁。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_class(db_mode, class_name="软件2601"):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass

    db = get_sessionmaker()()
    row = SchoolClass(
        tenant_id=TID,
        major_id=1,
        class_name=class_name,
        grade="2026",
        status="ACTIVE",
    )
    db.add(row)
    db.flush()
    value = int(row.id)
    db.commit()
    db.close()
    return value


def _seed_student(db_mode, student_no="R001", class_id=None):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile

    db = get_sessionmaker()()
    row = StudentProfile(
        tenant_id=TID,
        student_no=student_no,
        real_name=f"学籍{student_no}",
        class_id=class_id,
        current_stage="ON_CAMPUS",
        student_status="REGISTERED",
        status="ACTIVE",
        id_card_encrypted=f"ENC-{student_no}",
    )
    db.add(row)
    db.flush()
    value = int(row.id)
    db.commit()
    db.close()
    return value


def _seed_term(db_mode, *, year_code="2026-2027"):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm

    db = get_sessionmaker()()
    row = AaTerm(
        tenant_id=TID,
        year_code=year_code,
        term_no=1,
        term_name=f"{year_code}第1学期",
        teaching_weeks=18,
        status="PUBLISHED",
        is_current=True,
    )
    db.add(row)
    db.flush()
    value = int(row.id)
    db.commit()
    db.close()
    return value


def _seed_course(code, name, *, credit=3):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    db = get_sessionmaker()()
    row = AaCourse(
        tenant_id=TID,
        course_code=code,
        course_name=name,
        credit=credit,
        nature="REQUIRED",
        category="MAJOR_CORE",
        status="ENABLED",
    )
    db.add(row)
    db.flush()
    value = int(row.id)
    db.commit()
    db.close()
    return value


def _ensure_slot(slot_no):
    from app.db.session import get_sessionmaker
    from app.models import AaTimeSlot

    db = get_sessionmaker()()
    row = db.query(AaTimeSlot).filter(
        AaTimeSlot.tenant_id == TID,
        AaTimeSlot.slot_no == int(slot_no),
        AaTimeSlot.is_deleted.is_(False),
    ).first()
    if row is None:
        db.add(AaTimeSlot(
            tenant_id=TID,
            slot_no=int(slot_no),
            slot_name=f"第{slot_no}节",
            enabled=True,
            status="ENABLED",
        ))
    else:
        row.enabled = True
        row.status = "ENABLED"
    db.commit()
    db.close()


def _seed_ready_task(
    term_id,
    class_id,
    code,
    course_name,
    *,
    teacher_key,
    teacher_name,
    slot_no=1,
    teaching_class_code=None,
    teaching_class_name=None,
):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch

    course_id = _seed_course(code, course_name)
    _ensure_slot(slot_no)
    db = get_sessionmaker()()
    course = db.get(AaCourse, int(course_id))
    batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=int(term_id),
        batch_name=f"{course_name}教学任务批次",
        status="APPROVED",
    )
    db.add(batch)
    db.flush()
    task = AaTeachingTask(
        tenant_id=TID,
        batch_id=batch.id,
        course_id=course.id,
        course_code=course.course_code,
        course_name=course.course_name,
        class_id=int(class_id) if class_id else None,
        teaching_class_code=teaching_class_code,
        teaching_class_name=teaching_class_name or (f"{course_name}教学班" if class_id else None),
        teacher_key=teacher_key,
        teacher_name=teacher_name,
        weekly_hours=1,
        start_week=1,
        end_week=18,
        status="READY",
    )
    db.add(task)
    db.flush()
    value = int(task.id)
    db.commit()
    db.close()
    return value


def _admin_grade_task(client, hdr, db_mode, *, class_id, code, course_name):
    term_id = _seed_term(db_mode)
    course_id = _seed_course(code, course_name)
    response = client.post(
        f"{BASE}/grade-tasks",
        headers=hdr,
        json={
            "termId": str(term_id),
            "courseId": str(course_id),
            "courseName": course_name,
            "classId": str(class_id),
            "usualRatio": 30,
            "finalRatio": 70,
            "adminSupplementReason": "测试管理员特殊补录成绩任务",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["gradeTaskId"]


def _add_schedule_item(client, hdr, batch_id, task_id, *, weekday, slot_no):
    response = client.post(
        f"{BASE}/schedule-batches/{batch_id}/items",
        headers=hdr,
        json={
            "taskId": str(task_id),
            "weekday": weekday,
            "slotNo": slot_no,
            "startWeek": 1,
            "endWeek": 18,
            "weekParity": "ALL",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _publish_schedule(client, hdr, batch_id):
    pre = client.post(f"{BASE}/schedule-batches/{batch_id}/pre-publish", headers=hdr)
    assert pre.status_code == 200, pre.text
    published = client.post(f"{BASE}/schedule-batches/{batch_id}/publish", headers=hdr)
    assert published.status_code == 200, published.text


def test_roster_detail_reveal_and_status_summary(client, db_mode):
    cid = _seed_class(db_mode)
    sid = _seed_student(db_mode, "R001", cid)
    hdr = _hdr(client, "school_admin01")
    detail = client.get(f"{BASE}/roster/{sid}", headers=hdr)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["studentNo"] == "R001"
    assert detail.json()["data"]["studentStatus"] == "REGISTERED"
    reveal = client.post(
        f"{BASE}/roster/{sid}/reveal",
        headers=hdr,
        json={"reason": "核对身份信息"},
    )
    assert reveal.status_code == 200, reveal.text
    assert reveal.json()["data"]["idCard"] == "ENC-R001"
    summary = client.get(f"{BASE}/roster/status-summary", headers=hdr)
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert data["total"] >= 1
    assert any(row["status"] == "REGISTERED" for row in data["byStatus"])


def test_roster_detail_student_forbidden_403(client, db_mode):
    sid = _seed_student(db_mode, "R001")
    from app.core.security import create_access_token

    stu_hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-R001",
        "realName": "学籍R001",
        "studentNo": "R001",
        "userType": "STUDENT",
        "tid": "x",
        "tenantId": str(TID),
        "activeContextId": "ctx",
        "currentRoleCode": "STUDENT",
        "clientType": "MP",
    })}
    assert client.get(f"{BASE}/roster/{sid}", headers=stu_hdr).status_code == 403


def test_grade_import_confirm_writes_records(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    class_id = _seed_class(db_mode, "成绩导入2601")
    _seed_student(db_mode, "IMPORT01", class_id)
    task_id = _admin_grade_task(
        client, hdr, db_mode,
        class_id=class_id, code="T1G101", course_name="线性代数",
    )
    rows = [{"studentNo": "IMPORT01", "usualScore": 80, "finalScore": 80}]
    confirm = client.post(
        f"{BASE}/grade-tasks/{task_id}/import/confirm",
        headers=hdr,
        json={"rows": rows},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["data"]["created"] == 1
    records = client.get(f"{BASE}/grade-tasks/{task_id}/records", headers=hdr)
    assert records.status_code == 200, records.text
    items = records.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["studentNo"] == "IMPORT01"
    assert items[0]["totalScore"] == 80


def test_grade_import_confirm_unmatched_student_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    class_id = _seed_class(db_mode, "成绩导入2602")
    _seed_student(db_mode, "KNOWN01", class_id)
    task_id = _admin_grade_task(
        client, hdr, db_mode,
        class_id=class_id, code="T1G102", course_name="线性代数",
    )
    rows = [{"studentNo": "NOBODY", "usualScore": 80, "finalScore": 75}]
    confirm = client.post(
        f"{BASE}/grade-tasks/{task_id}/import/confirm",
        headers=hdr,
        json={"rows": rows},
    )
    assert confirm.status_code == 409, confirm.text


def test_schedule_readonly_views_and_publish_records(client, db_mode):
    term_id = _seed_term(db_mode)
    class_id = _seed_class(db_mode)
    hdr = _hdr(client, "school_admin01")
    task_id = _seed_ready_task(
        term_id, class_id, "T1S101", "大学英语",
        teacher_key="T001", teacher_name="王老师", slot_no=1,
        teaching_class_name="大学英语(软件2601)",
    )
    batch_id = client.post(
        f"{BASE}/schedule-batches",
        headers=hdr,
        json={"termId": str(term_id), "batchName": "2026秋课表"},
    ).json()["data"]["batchId"]
    _add_schedule_item(client, hdr, batch_id, task_id, weekday=1, slot_no=1)
    _publish_schedule(client, hdr, batch_id)

    cls = client.get(f"{BASE}/schedule/class/{class_id}", headers=hdr)
    assert cls.status_code == 200, cls.text
    assert len(cls.json()["data"]["items"]) == 1
    teacher = client.get(f"{BASE}/schedule/teacher/T001", headers=hdr)
    assert teacher.status_code == 200, teacher.text
    assert teacher.json()["data"]["weeklyHours"] == 1
    records = client.get(f"{BASE}/schedule/publish-records", headers=hdr)
    assert records.status_code == 200, records.text
    assert records.json()["data"]["total"] >= 1


def test_evaluation_self_role_tasks_generate_and_list(client, db_mode):
    term_id = _seed_term(db_mode)
    class_id = _seed_class(db_mode, "评教2601")
    task_id = _seed_ready_task(
        term_id, class_id, "T1E101", "数据结构",
        teacher_key="T002", teacher_name="李老师",
        teaching_class_name="数据结构(评教2601)",
    )
    hdr = _hdr(client, "school_admin01")
    created = client.post(
        f"{BASE}/evaluation/batches",
        headers=hdr,
        json={
            "batchName": "2026秋评教",
            "termId": str(term_id),
            "anonymous": True,
        },
    )
    assert created.status_code == 200, created.text
    batch_id = created.json()["data"]["batchId"]
    generated = client.post(
        f"{BASE}/evaluation/batches/{batch_id}/role-tasks",
        headers=hdr,
        json={"evaluatorType": "SELF", "assignments": [{"teachingTaskId": str(task_id)}]},
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["data"]["taskCount"] == 1
    mine = client.get(
        f"{BASE}/evaluation/my-role-tasks",
        headers=hdr,
        params={"evaluatorType": "SELF", "batchId": batch_id},
    )
    assert mine.status_code == 200, mine.text


def test_student_schedule_view_and_out_of_scope_403(client, db_mode):
    term_id = _seed_term(db_mode)
    class_id = _seed_class(db_mode, "软件2602")
    student_id = _seed_student(db_mode, "STU301", class_id)
    hdr = _hdr(client, "school_admin01")
    task_id = _seed_ready_task(
        term_id, class_id, "T1S102", "高等数学",
        teacher_key="T101", teacher_name="赵老师", slot_no=1,
        teaching_class_name="高等数学(软件2602)",
    )
    batch_id = client.post(
        f"{BASE}/schedule-batches",
        headers=hdr,
        json={"termId": str(term_id), "batchName": "2026秋课表-学生"},
    ).json()["data"]["batchId"]
    _add_schedule_item(client, hdr, batch_id, task_id, weekday=2, slot_no=1)
    _publish_schedule(client, hdr, batch_id)

    student_view = client.get(f"{BASE}/schedule/student/{student_id}", headers=hdr)
    assert student_view.status_code == 200, student_view.text
    data = student_view.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["courseName"] == "高等数学"
    assert data["studentNo"] == "STU301"

    from app.core.security import create_access_token
    college_hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-college-noscope",
        "realName": "无范围学院教务",
        "userType": "STAFF",
        "tid": "x",
        "tenantId": str(TID),
        "activeContextId": "ctx_college_noscope",
        "currentRoleCode": "COLLEGE_ADMIN",
        "clientType": "PC",
    })}
    forbidden = client.get(f"{BASE}/schedule/student/{student_id}", headers=college_hdr)
    assert forbidden.status_code == 403, forbidden.text


def test_teaching_class_schedule_view_and_not_found_404(client, db_mode):
    term_id = _seed_term(db_mode)
    class_id = _seed_class(db_mode, "软件2603")
    hdr = _hdr(client, "school_admin01")
    code = "TC-TEST-0001"
    task_id = _seed_ready_task(
        term_id, class_id, "T1S103", "大学物理",
        teacher_key="T102", teacher_name="钱老师", slot_no=2,
        teaching_class_code=code,
        teaching_class_name="大学物理(软件2603)",
    )
    batch_id = client.post(
        f"{BASE}/schedule-batches",
        headers=hdr,
        json={"termId": str(term_id), "batchName": "2026秋课表-教学班"},
    ).json()["data"]["batchId"]
    _add_schedule_item(client, hdr, batch_id, task_id, weekday=3, slot_no=2)
    _publish_schedule(client, hdr, batch_id)

    view = client.get(f"{BASE}/schedule/teaching-class/{code}", headers=hdr)
    assert view.status_code == 200, view.text
    data = view.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["courseName"] == "大学物理"
    assert data["teachingClassName"] == "大学物理(软件2603)"

    missing = client.get(f"{BASE}/schedule/teaching-class/TC-NOPE-0000", headers=hdr)
    assert missing.status_code == 404, missing.text


def test_schedule_adjustments_log_and_invalid_biz_type_400(client, db_mode):
    term_id = _seed_term(db_mode)
    class_id = _seed_class(db_mode, "软件2604")
    hdr = _hdr(client, "school_admin01")
    task_id = _seed_ready_task(
        term_id, class_id, "T1S104", "大学英语",
        teacher_key="T103", teacher_name="孙老师", slot_no=1,
        teaching_class_name="大学英语(软件2604)",
    )
    batch_id = client.post(
        f"{BASE}/schedule-batches",
        headers=hdr,
        json={"termId": str(term_id), "batchName": "2026秋课表-调整记录"},
    ).json()["data"]["batchId"]
    _add_schedule_item(client, hdr, batch_id, task_id, weekday=4, slot_no=1)

    logs = client.get(
        f"{BASE}/schedule/adjustments",
        headers=hdr,
        params={"bizType": "AA_SCHEDULE"},
    )
    assert logs.status_code == 200, logs.text
    data = logs.json()["data"]
    assert data["total"] >= 1
    assert any(row["action"] == "ADD_ITEM" for row in data["items"])

    bad = client.get(
        f"{BASE}/schedule/adjustments",
        headers=hdr,
        params={"bizType": "AA_SCHEDULE_CHANGE"},
    )
    assert bad.status_code == 400, bad.text
