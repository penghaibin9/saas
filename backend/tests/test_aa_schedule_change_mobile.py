"""教务中心 · 移动端调停课。

移动端继续只包装正式调停课能力；测试夹具必须与 PC 权威合同一致：真实组织树、正式已发布学期、
READY 教学任务、课位回链 taskId，并先 pre-publish 再 publish。不能用 termId=1 / major_id=1
等旧最小夹具让正式前置校验提前失败。
"""
from __future__ import annotations

from datetime import date, timedelta

MOB = "/api/v1/mobile"
BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass

    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="移动调停课学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="移动调停课软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name="软件2801", grade="2028", status="ACTIVE",
    )
    db.add(klass); db.flush()
    ids = {"class": int(klass.id)}
    db.commit(); db.close()
    return ids


def _term(client, hdr):
    start = date(2028, 9, 1)
    created = client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": "2028-2029", "termNo": 1, "termName": "移动调停课回归学期",
        "startDate": start.isoformat(), "endDate": (start + timedelta(days=200)).isoformat(),
        "teachingWeeks": 18,
    })
    assert created.status_code == 200, created.text
    term_id = created.json()["data"]["termId"]
    published = client.post(f"{BASE}/terms/{term_id}/publish", headers=hdr)
    assert published.status_code == 200, published.text

    from app.db.session import get_sessionmaker
    from app.models import AaTimeSlot

    db = get_sessionmaker()()
    for slot_no, start_time, end_time in [(1, "08:00", "08:45"), (2, "08:55", "09:40")]:
        row = db.query(AaTimeSlot).filter(
            AaTimeSlot.tenant_id == TID,
            AaTimeSlot.slot_no == slot_no,
            AaTimeSlot.is_deleted.is_(False),
        ).first()
        if row is None:
            db.add(AaTimeSlot(
                tenant_id=TID, slot_no=slot_no, slot_name=f"第{slot_no}节",
                start_time=start_time, end_time=end_time, enabled=True, status="ENABLED",
            ))
        else:
            row.start_time, row.end_time = start_time, end_time
            row.enabled, row.status = True, "ENABLED"
    db.commit(); db.close()
    return str(term_id)


def _batch(client, hdr):
    term_id = _term(client, hdr)
    response = client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": term_id})
    assert response.status_code == 200, response.text
    return response.json()["data"]["batchId"]


def _ready_task(bid, class_id, teacher_key, teacher_name, course_name):
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaScheduleBatch, AaTeachingTask, AaTeachingTaskBatch,
                            Major, SchoolClass)
    from tests.support_schedule_change_identity import seed_schedule_change_identity

    db = get_sessionmaker()()
    schedule_batch = db.get(AaScheduleBatch, int(bid))
    assert schedule_batch is not None
    cls = db.get(SchoolClass, int(class_id))
    assert cls is not None
    major = db.get(Major, int(cls.major_id)) if cls.major_id else None
    assert major is not None and major.college_id
    college_id = int(major.college_id)
    seed_schedule_change_identity(db, college_ids=[college_id])

    seq = db.query(AaTeachingTask).filter(AaTeachingTask.tenant_id == TID).count() + 201
    course_code = f"MSC{seq:03d}"
    course = AaCourse(
        tenant_id=TID, course_code=course_code, course_name=course_name,
        nature="REQUIRED", credit=4, status="ENABLED",
    )
    db.add(course); db.flush()
    task_batch = AaTeachingTaskBatch(
        tenant_id=TID, term_id=int(schedule_batch.term_id),
        batch_name=f"移动调停课教学任务批次-{seq}", college_id=college_id, status="APPROVED",
    )
    db.add(task_batch); db.flush()
    task = AaTeachingTask(
        tenant_id=TID, batch_id=task_batch.id, course_id=course.id,
        course_code=course_code, course_name=course_name,
        class_id=int(class_id), teaching_class_name=cls.class_name,
        teacher_key=teacher_key, teacher_name=teacher_name,
        status="READY", weekly_hours=1, total_hours=18, start_week=1, end_week=18,
    )
    db.add(task); db.flush()
    task_id = int(task.id)
    db.commit(); db.close()
    return task_id


def _item(client, hdr, bid, class_id, **kw):
    body = {"weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
            "teacherKey": "academic01", "teacherName": "赵敏", "classId": str(class_id),
            "className": "软件2801", "classroom": "A101", "courseName": "高等数学"}
    body.update(kw)
    body["taskId"] = str(_ready_task(
        bid, int(body["classId"]), body["teacherKey"], body["teacherName"], body["courseName"]
    ))
    response = client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]["itemId"]


def _published_item(client, hdr, cid, teacher_key="academic01", teacher_name="赵敏"):
    bid = _batch(client, hdr)
    origin = _item(client, hdr, bid, cid, teacherKey=teacher_key, teacherName=teacher_name)
    prepublished = client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=hdr)
    assert prepublished.status_code == 200, prepublished.text
    published = client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    assert published.status_code == 200, published.text
    return bid, origin


def test_my_schedule_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])

    r = client.get(f"{MOB}/teacher/academic/schedule/mine", headers=_hdr(client, "academic01")).json()
    assert r["code"] == 0
    assert any(i["itemId"] == origin for i in r["data"]["items"])


def test_conflict_check_and_submit_flow_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    hdr = _hdr(client, "academic01")

    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2}
    chk = client.post(f"{MOB}/teacher/academic/schedule-changes/conflict-check", headers=hdr, json=body).json()
    assert chk["code"] == 0 and chk["data"]["conflict"] is None

    sub = client.post(f"{MOB}/teacher/academic/schedule-changes", headers=hdr, json=body)
    assert sub.status_code == 200 and sub.json()["data"]["status"] == "SUBMITTED"
    change_id = sub.json()["data"]["changeId"]

    lst = client.get(f"{MOB}/teacher/academic/schedule-changes", headers=hdr).json()["data"]["list"]
    assert any(c["changeId"] == change_id for c in lst)


def test_cancel_flow_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    hdr = _hdr(client, "academic01")
    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2}
    change_id = client.post(f"{MOB}/teacher/academic/schedule-changes", headers=hdr, json=body).json()["data"]["changeId"]

    r = client.post(f"{MOB}/teacher/academic/schedule-changes/{change_id}/cancel", headers=hdr,
                    json={"reason": "计划变更"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "CANCELLED"


def test_cross_scope_submit_403_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"], teacher_key="other_teacher", teacher_name="他人")
    hdr = _hdr(client, "academic01")
    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2}
    r = client.post(f"{MOB}/teacher/academic/schedule-changes", headers=hdr, json=body)
    assert r.status_code == 403


def test_detail_ownership_guard_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    hdr = _hdr(client, "academic01")
    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2}
    change_id = client.post(f"{MOB}/teacher/academic/schedule-changes", headers=hdr, json=body).json()["data"]["changeId"]

    ok = client.get(f"{MOB}/teacher/academic/schedule-changes/{change_id}", headers=hdr)
    assert ok.status_code == 200 and ok.json()["data"]["changeId"] == change_id

    other_hdr = _hdr(client, "teacher01")
    forbidden = client.get(f"{MOB}/teacher/academic/schedule-changes/{change_id}", headers=other_hdr)
    assert forbidden.status_code == 403
