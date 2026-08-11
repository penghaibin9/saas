"""拖拽调格（/academic-affairs/schedule-items/{id}/move）+ 排考时间自动编排（/exam/batches/{id}/auto-times）测试。

任务6：move 走同一三重冲突检测器（冲突 409 原位不动）；AUTO 项被人工拖动后转 MANUAL 保护。
任务7：时间网格分配（同班同时段不撞/每日限考/教师不撞）；增量不动已定时间；时段不足如实报。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


# ── 任务6：拖拽调格 ──

def _seed_schedule(db_mode):
    """按最终课表合同种正式学期、启用节次、APPROVED任务批次和READY教学任务。"""
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse, AaScheduleBatch, AaScheduleItem, AaTeachingTask,
        AaTeachingTaskBatch, AaTerm, AaTimeSlot,
    )

    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2097-2098", term_no=1,
                  teaching_weeks=18, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    for slot_no in (1, 3, 5):
        db.add(AaTimeSlot(tenant_id=TID, slot_no=slot_no, slot_name=f"第{slot_no}节",
                          enabled=True, status="ENABLED"))
    task_batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id,
                                     batch_name="拖拽测试教学任务批次", status="APPROVED")
    db.add(task_batch); db.flush()
    c1 = AaCourse(tenant_id=TID, course_code="MOVE101", course_name="高数", credit=4, status="ENABLED")
    c2 = AaCourse(tenant_id=TID, course_code="MOVE102", course_name="英语", credit=4, status="ENABLED")
    db.add_all([c1, c2]); db.flush()
    # 两个任务用同一教师：原位不冲突；把 i1 拖到周二第3节时形成真实教师冲突。
    t1 = AaTeachingTask(tenant_id=TID, batch_id=task_batch.id, course_id=c1.id,
                        course_code=c1.course_code, course_name=c1.course_name,
                        teacher_key="t01", teacher_name="王老师", weekly_hours=1,
                        start_week=1, end_week=18, status="READY")
    t2 = AaTeachingTask(tenant_id=TID, batch_id=task_batch.id, course_id=c2.id,
                        course_code=c2.course_code, course_name=c2.course_name,
                        teacher_key="t01", teacher_name="王老师", weekly_hours=1,
                        start_week=1, end_week=18, status="READY")
    db.add_all([t1, t2]); db.flush()
    b = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="拖拽测试批次", status="DRAFT")
    db.add(b); db.flush()
    i1 = AaScheduleItem(tenant_id=TID, batch_id=b.id, task_id=t1.id, course_id=c1.id,
                        course_name=c1.course_name, teacher_key=t1.teacher_key, teacher_name=t1.teacher_name,
                        weekday=1, slot_no=1, start_week=1, end_week=18, week_parity="ALL",
                        classroom_text="A101", status="EFFECTIVE", source="AUTO")
    i2 = AaScheduleItem(tenant_id=TID, batch_id=b.id, task_id=t2.id, course_id=c2.id,
                        course_name=c2.course_name, teacher_key=t2.teacher_key, teacher_name=t2.teacher_name,
                        weekday=2, slot_no=3, start_week=1, end_week=18, week_parity="ALL",
                        classroom_text="A102", status="EFFECTIVE", source="MANUAL")
    db.add_all([i1, i2]); db.commit()
    ids = {"batch": b.id, "auto_item": i1.id, "manual_item": i2.id}
    db.close()
    return ids


def test_move_ok_and_auto_becomes_manual(client, db_mode):
    ids = _seed_schedule(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.put(f"{BASE}/schedule-items/{ids['auto_item']}/move", headers=admin,
                   json={"weekday": 3, "slotNo": 5})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["weekday"] == 3 and data["slotNo"] == 5
    assert data["prePublishReset"] is False
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    db = get_sessionmaker()()
    it = db.get(AaScheduleItem, ids["auto_item"])
    db.close()
    assert it.weekday == 3 and it.slot_no == 5
    assert it.source == "MANUAL", "自动项被人工拖动后必须转 MANUAL（重排保护）"


def test_move_conflict_409_stays_put(client, db_mode):
    """拖到与同教师另一课程同时段 → 409 且原位不动。"""
    ids = _seed_schedule(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.put(f"{BASE}/schedule-items/{ids['auto_item']}/move", headers=admin,
                   json={"weekday": 2, "slotNo": 3})
    assert r.status_code == 409, r.text
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    db = get_sessionmaker()()
    it = db.get(AaScheduleItem, ids["auto_item"])
    db.close()
    assert it.weekday == 1 and it.slot_no == 1, "冲突时必须原位不动"


# ── 任务7：排考时间自动编排 ──

def _seed_exam_times(db_mode):
    """同一班级两门课 + 另一班级一门课（共用 grade 種子结构，直接建考务批次课程）。"""
    from app.db.session import get_sessionmaker
    from app.models import AaExamBatch, AaExamCourse
    db = get_sessionmaker()()
    b = AaExamBatch(tenant_id=TID, batch_name="定时测试批次", status="COURSE_CONFIRMED")
    db.add(b); db.flush()
    c1 = AaExamCourse(tenant_id=TID, batch_id=b.id, teaching_task_id=901, course_name="高数",
                      class_id=11, class_name="软件2401", teacher_key="t01",
                      expected_students=50, status="CONFIRMED")
    c2 = AaExamCourse(tenant_id=TID, batch_id=b.id, teaching_task_id=902, course_name="英语",
                      class_id=11, class_name="软件2401", teacher_key="t02",
                      expected_students=50, status="CONFIRMED")
    c3 = AaExamCourse(tenant_id=TID, batch_id=b.id, teaching_task_id=903, course_name="体育",
                      class_id=22, class_name="软件2402", teacher_key="t03",
                      expected_students=40, status="CONFIRMED")
    db.add_all([c1, c2, c3]); db.commit()
    ids = {"batch": b.id, "c1": c1.id, "c2": c2.id, "c3": c3.id}
    db.close()
    return ids


_TIMES = {"dates": ["2027-06-20", "2027-06-21"],
          "sessions": [{"start": "09:00", "end": "11:00"}],
          "maxPerDayPerClass": 1}


def test_auto_times_class_no_clash(client, db_mode):
    """同班两门课 + 每日一场 → 必须分到不同日期；异班可同时段。"""
    ids = _seed_exam_times(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/exam/batches/{ids['batch']}/auto-times", headers=admin, json=_TIMES)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["assigned"] == 3 and d["missed"] == 0, d
    from app.db.session import get_sessionmaker
    from app.models import AaExamCourse
    db = get_sessionmaker()()
    c1 = db.get(AaExamCourse, ids["c1"]); c2 = db.get(AaExamCourse, ids["c2"])
    db.close()
    assert c1.exam_date != c2.exam_date, "同班级两门课不得同一天（每日限考1场）"


def test_auto_times_incremental_and_shortage(client, db_mode):
    """已定时间的课程不动；时段不足如实报 NO_SESSION。"""
    ids = _seed_exam_times(db_mode)
    admin = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import AaExamCourse
    db = get_sessionmaker()()
    c1 = db.get(AaExamCourse, ids["c1"])
    c1.exam_date, c1.start_time, c1.end_time = "2027-06-20", "09:00", "11:00"
    db.commit(); db.close()
    body = {"dates": ["2027-06-20"], "sessions": [{"start": "09:00", "end": "11:00"}],
            "maxPerDayPerClass": 1}
    d = client.post(f"{BASE}/exam/batches/{ids['batch']}/auto-times", headers=admin,
                    json=body).json()["data"]
    assert d["assigned"] == 1 and d["missed"] == 1
    assert d["misses"][0]["reason"] == "NO_SESSION"
    db = get_sessionmaker()()
    c1 = db.get(AaExamCourse, ids["c1"])
    db.close()
    assert c1.exam_date == "2027-06-20" and c1.start_time == "09:00", "已定时间不得被改动"
