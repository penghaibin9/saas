from __future__ import annotations

from datetime import date, datetime
import inspect

TID = 1000000000000007310


def _ctx():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "u_CW2-T1",
        "tenantId": str(TID),
        "realName": "C-W2教师",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "activeContextId": "ctx_CW2-T1",
        "loginName": "CW2-T1",
        "userType": "STAFF",
    })


def _user():
    return {
        "userType": "STAFF",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "loginName": "CW2-T1",
        "userId": "u_CW2-T1",
        "activeContextId": "ctx_CW2-T1",
    }


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed(db):
    from app.models import (
        AaCourse,
        AaScheduleBatch,
        AaScheduleItem,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        College,
        Major,
        SchoolClass,
    )
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth

    college = College(tenant_id=TID, college_name="C-W2学院", code="CW2-COL", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(
        tenant_id=TID,
        college_id=college.id,
        major_name="C-W2专业",
        code="CW2-MAJOR",
        status="ACTIVE",
    )
    db.add(major)
    db.flush()
    school_class = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name="C-W2测试班",
        grade="2026",
        status="ACTIVE",
        class_status="NORMAL",
    )
    db.add(school_class)
    db.flush()

    term = AaTerm(
        tenant_id=TID,
        year_code="2026-2027",
        term_no=1,
        term_name="C-W2 Teacher Today 学期",
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 7, 5),
        teaching_weeks=18,
        is_current=True,
        status="PUBLISHED",
    )
    db.add(term)
    db.flush()

    active_course = AaCourse(
        tenant_id=TID,
        course_code="CW2-ACTIVE",
        course_name="当前正式课程",
        credit=2,
        status="ENABLED",
    )
    rogue_course = AaCourse(
        tenant_id=TID,
        course_code="CW2-ROGUE",
        course_name="非Authority最近发布课程",
        credit=2,
        status="ENABLED",
    )
    db.add_all([active_course, rogue_course])
    db.flush()

    task_batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=college.id,
        batch_name="C-W2教学任务批次",
        status="APPROVED",
    )
    db.add(task_batch)
    db.flush()

    active_task = AaTeachingTask(
        tenant_id=TID,
        batch_id=task_batch.id,
        course_id=active_course.id,
        course_code=active_course.course_code,
        course_name=active_course.course_name,
        teacher_key="CW2-T1",
        teacher_name="C-W2教师",
        class_id=school_class.id,
        teaching_class_name=school_class.class_name,
        status="READY",
        weekly_hours=2,
        total_hours=36,
        start_week=1,
        end_week=18,
    )
    rogue_task = AaTeachingTask(
        tenant_id=TID,
        batch_id=task_batch.id,
        course_id=rogue_course.id,
        course_code=rogue_course.course_code,
        course_name=rogue_course.course_name,
        teacher_key="CW2-T1",
        teacher_name="C-W2教师",
        class_id=school_class.id,
        teaching_class_name=school_class.class_name,
        status="READY",
        weekly_hours=2,
        total_hours=36,
        start_week=1,
        end_week=18,
    )
    db.add_all([active_task, rogue_task])
    db.flush()

    active_batch = AaScheduleBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=college.id,
        batch_name="C-W2当前ScopeHead课表",
        status="PUBLISHED",
        publish_at=datetime(2026, 2, 20, 8, 0, 0),
    )
    rogue_batch = AaScheduleBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=college.id,
        batch_name="C-W2更晚但非Authority课表",
        status="PUBLISHED",
        publish_at=datetime(2026, 2, 21, 8, 0, 0),
    )
    db.add_all([active_batch, rogue_batch])
    db.flush()

    active_item = AaScheduleItem(
        tenant_id=TID,
        batch_id=active_batch.id,
        task_id=active_task.id,
        course_id=active_course.id,
        course_name=active_course.course_name,
        teacher_key=active_task.teacher_key,
        teacher_name=active_task.teacher_name,
        class_id=school_class.id,
        class_name=school_class.class_name,
        classroom_text="A101",
        weekday=1,
        slot_no=2,
        start_week=1,
        end_week=18,
        week_parity="ALL",
        status="EFFECTIVE",
    )
    rogue_item = AaScheduleItem(
        tenant_id=TID,
        batch_id=rogue_batch.id,
        task_id=rogue_task.id,
        course_id=rogue_course.id,
        course_name=rogue_course.course_name,
        teacher_key=rogue_task.teacher_key,
        teacher_name=rogue_task.teacher_name,
        class_id=school_class.id,
        class_name=school_class.class_name,
        classroom_text="B202",
        weekday=1,
        slot_no=3,
        start_week=1,
        end_week=18,
        week_parity="ALL",
        status="EFFECTIVE",
    )
    db.add_all([active_item, rogue_item])
    db.flush()

    head = truth.lock_scope_head(db, term.id, "COLLEGE", college.id)
    head.active_batch_id = active_batch.id
    head.version = 11
    head.published_at = datetime(2026, 2, 20, 8, 0, 0)
    db.flush()
    return term, active_task, active_batch, active_item, rogue_batch, rogue_item


def test_teacher_schedule_projection_consumes_scopehead_not_latest_published(db_mode):
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    _ctx()
    db = _session()
    _term, active_task, active_batch, active_item, rogue_batch, rogue_item = _seed(db)
    db.commit()
    db.close()

    result = today.teacher_schedule_projection(_user())
    assert result["hasData"] is True
    assert result["issues"] == []
    assert [row["scheduleItemId"] for row in result["items"]] == [str(active_item.id)]
    row = result["items"][0]
    assert row["activeBatchId"] == str(active_batch.id)
    assert row["teachingTaskId"] == str(active_task.id)
    assert row["scopeType"] == "COLLEGE"
    assert row["scopeHeadVersion"] == 11
    assert row["classroom"] == "A101"
    assert str(rogue_batch.id) != row["activeBatchId"]
    assert str(rogue_item.id) not in {item["scheduleItemId"] for item in result["items"]}


def test_teacher_today_builds_exact_attendance_deep_link_from_formal_occurrence(db_mode):
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    _ctx()
    db = _session()
    _term, active_task, _active_batch, active_item, _rogue_batch, _rogue_item = _seed(db)
    db.commit()
    db.close()

    result = today.teacher_today_projection(_user(), on_date=date(2026, 3, 2))
    assert result["calendarSource"] == "NORMAL"
    assert result["logicalDate"] == "2026-03-02"
    assert result["currentWeek"] == 1
    assert len(result["todayItems"]) == 1
    row = result["todayItems"][0]
    assert row["scheduleItemId"] == str(active_item.id)
    assert row["teachingTaskId"] == str(active_task.id)
    assert row["sessionDate"] == "2026-03-02"
    assert row["attendanceRoute"] == (
        "/pages/teacher/academic-affairs/attendance"
        f"?teachingTaskId={active_task.id}&sessionDate=2026-03-02"
        f"&slotNo=2&scheduleItemId={active_item.id}"
    )


def test_teacher_today_holiday_is_empty_without_falling_back_to_another_course(db_mode):
    from app.models import AaCalendarEvent
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    _ctx()
    db = _session()
    term, _task, _batch, _item, _rogue_batch, _rogue_item = _seed(db)
    db.add(AaCalendarEvent(
        tenant_id=TID,
        term_id=term.id,
        event_type="HOLIDAY",
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 3, 2),
        remark="C-W2节假日",
    ))
    db.commit()
    db.close()

    result = today.teacher_today_projection(_user(), on_date=date(2026, 3, 2))
    assert result["calendarSource"] == "HOLIDAY"
    assert result["todayItems"] == []


def test_teacher_today_swap_target_uses_logical_day_but_routes_actual_day(db_mode):
    from app.models import AaCalendarEvent
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    _ctx()
    db = _session()
    term, active_task, _batch, active_item, _rogue_batch, _rogue_item = _seed(db)
    swap = AaCalendarEvent(
        tenant_id=TID,
        term_id=term.id,
        event_type="SWAP",
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 3, 2),
        swap_to_date=datetime(2026, 3, 3),
        remark="周一课程调至周二上课",
    )
    db.add(swap)
    db.commit()
    swap_id = swap.id
    db.close()

    result = today.teacher_today_projection(_user(), on_date=date(2026, 3, 3))
    assert result["calendarSource"] == "SWAP"
    assert result["calendarEventId"] == str(swap_id)
    assert result["logicalDate"] == "2026-03-02"
    assert result["currentWeek"] == 1
    assert len(result["todayItems"]) == 1
    row = result["todayItems"][0]
    assert row["scheduleItemId"] == str(active_item.id)
    assert row["sessionDate"] == "2026-03-03"
    assert row["attendanceRoute"] == (
        "/pages/teacher/academic-affairs/attendance"
        f"?teachingTaskId={active_task.id}&sessionDate=2026-03-03"
        f"&slotNo=2&scheduleItemId={active_item.id}"
    )


def test_teacher_today_reuses_c_c1_batched_occurrence_projection():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    source = inspect.getsource(today._teacher_schedule_in_session)
    assert "formal_schedule_patterns_for_tasks" in source
    assert "resolve_formal_occurrence" not in source
    assert "AaScheduleScopeHead" not in source
    assert "status == \"PUBLISHED\"" not in source
