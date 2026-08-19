from __future__ import annotations

from datetime import datetime
import inspect

TID = 1000000000000007300


def _ctx():
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "u_CW1-T1",
        "tenantId": str(TID),
        "realName": "C-W1教师",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "activeContextId": "ctx-cw1-options",
        "loginName": "CW1-T1",
    })


def _user():
    return {
        "userType": "STAFF",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "loginName": "CW1-T1",
        "userId": "u_CW1-T1",
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

    college = College(tenant_id=TID, college_name="C-W1学院", code="CW1-COL", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(
        tenant_id=TID,
        college_id=college.id,
        major_name="C-W1专业",
        code="CW1-MAJOR",
        status="ACTIVE",
    )
    db.add(major); db.flush()
    school_class = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name="C-W1测试班",
        grade="2026",
        status="ACTIVE",
        class_status="NORMAL",
    )
    db.add(school_class); db.flush()

    term = AaTerm(
        tenant_id=TID,
        year_code="2026-2027",
        term_no=1,
        term_name="C-W1正式点名选项学期",
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 7, 5),
        teaching_weeks=18,
        is_current=True,
        status="PUBLISHED",
    )
    db.add(term); db.flush()

    course_ready = AaCourse(
        tenant_id=TID,
        course_code="CW1-OPT-READY",
        course_name="正式课表已发布课程",
        credit=2,
        status="ENABLED",
    )
    course_old = AaCourse(
        tenant_id=TID,
        course_code="CW1-OPT-OLD",
        course_name="仅历史课表课程",
        credit=2,
        status="ENABLED",
    )
    db.add_all([course_ready, course_old]); db.flush()

    task_batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=college.id,
        batch_name="C-W1点名选项教学任务批次",
        status="APPROVED",
    )
    db.add(task_batch); db.flush()

    task_ready = AaTeachingTask(
        tenant_id=TID,
        batch_id=task_batch.id,
        course_id=course_ready.id,
        course_code=course_ready.course_code,
        course_name=course_ready.course_name,
        teacher_key="CW1-T1",
        teacher_name="C-W1教师",
        class_id=school_class.id,
        status="APPROVED",
        weekly_hours=2,
        total_hours=36,
        start_week=1,
        end_week=18,
    )
    task_old = AaTeachingTask(
        tenant_id=TID,
        batch_id=task_batch.id,
        course_id=course_old.id,
        course_code=course_old.course_code,
        course_name=course_old.course_name,
        teacher_key="CW1-T1",
        teacher_name="C-W1教师",
        class_id=school_class.id,
        status="APPROVED",
        weekly_hours=2,
        total_hours=36,
        start_week=1,
        end_week=18,
    )
    db.add_all([task_ready, task_old]); db.flush()

    active_batch = AaScheduleBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=college.id,
        batch_name="C-W1当前正式课表",
        status="PUBLISHED",
    )
    historical_batch = AaScheduleBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=college.id,
        batch_name="C-W1历史课表",
        status="SUPERSEDED",
    )
    db.add_all([active_batch, historical_batch]); db.flush()

    ready_item = AaScheduleItem(
        tenant_id=TID,
        batch_id=active_batch.id,
        task_id=task_ready.id,
        course_id=course_ready.id,
        course_name=course_ready.course_name,
        teacher_key=task_ready.teacher_key,
        teacher_name=task_ready.teacher_name,
        class_id=school_class.id,
        class_name=school_class.class_name,
        weekday=1,
        slot_no=2,
        start_week=1,
        end_week=18,
        week_parity="ODD",
        status="EFFECTIVE",
    )
    old_item = AaScheduleItem(
        tenant_id=TID,
        batch_id=historical_batch.id,
        task_id=task_old.id,
        course_id=course_old.id,
        course_name=course_old.course_name,
        teacher_key=task_old.teacher_key,
        teacher_name=task_old.teacher_name,
        class_id=school_class.id,
        class_name=school_class.class_name,
        weekday=2,
        slot_no=3,
        start_week=1,
        end_week=18,
        week_parity="ALL",
        status="EFFECTIVE",
    )
    db.add_all([ready_item, old_item]); db.flush()

    head = truth.lock_scope_head(db, term.id, "COLLEGE", college.id)
    head.active_batch_id = active_batch.id
    head.version = 7
    head.published_at = datetime(2026, 2, 20, 8, 0, 0)
    db.flush()
    return term, task_ready, task_old, active_batch, ready_item


def test_attendance_class_options_expose_only_active_formal_schedule_patterns(db_mode):
    from app.modules.academic_affairs.services import mobile_academic_affairs_facade as facade

    _ctx()
    db = _session()
    term, task_ready, task_old, active_batch, ready_item = _seed(db)
    db.commit()
    db.close()

    result = facade.teacher_attendance_class_options(_user())
    by_task = {item["teachingTaskId"]: item for item in result["items"]}
    ready = by_task[str(task_ready.id)]

    assert result["termStartDate"] == "2026-03-02"
    assert result["termEndDate"] == "2026-07-05"
    assert result["teachingWeeks"] == 18

    assert ready["formalOccurrenceReady"] is True
    assert ready["formalScheduleStatus"] == "READY"
    assert ready["formalScheduleIssue"] == ""
    assert len(ready["formalSchedulePatterns"]) == 1
    pattern = ready["formalSchedulePatterns"][0]
    assert pattern == {
        "scheduleItemId": str(ready_item.id),
        "activeBatchId": str(active_batch.id),
        "scopeType": "COLLEGE",
        "scopeId": str(active_batch.college_id),
        "weekday": 1,
        "slotNo": 2,
        "startWeek": 1,
        "endWeek": 18,
        "weekParity": "ODD",
        "changeId": None,
        "changeType": None,
    }

    assert str(task_old.id) not in by_task


def test_attendance_class_options_uses_bounded_batch_projection_not_per_task_gets():
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today
    from app.modules.academic_affairs.services import mobile_academic_affairs_facade as facade

    picker_source = inspect.getsource(facade.teacher_attendance_class_options)
    projection_source = inspect.getsource(today._teacher_schedule_in_session)

    assert "teacher_schedule_projection" in picker_source
    assert "formal_schedule_patterns_for_tasks" in projection_source
    assert "db.get(AaTeachingTaskBatch" not in projection_source
    assert "db.get(SchoolClass" not in projection_source
    assert "AaTeachingTask.batch_id.in_(batch_ids)" in projection_source
    assert "SchoolClass.id.in_(class_ids)" in projection_source


def test_attendance_class_options_excludes_non_executable_task_even_with_formal_schedule(db_mode):
    from app.modules.academic_affairs.services import mobile_academic_affairs_facade as facade

    _ctx()
    db = _session()
    _term, task_ready, _task_old, _active_batch, _ready_item = _seed(db)
    task_ready.status = "ASSIGNED"
    db.commit()
    task_id = str(task_ready.id)
    db.close()

    result = facade.teacher_attendance_class_options(_user())
    assert task_id not in {item["teachingTaskId"] for item in result["items"]}


def test_attendance_class_options_reuses_canonical_task_execution_guard():
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as attendance
    from app.modules.academic_affairs.services import academic_affairs_attendance_teacher_relation_guard as command
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today

    assert attendance.ATTENDANCE_TASK_STATUSES == frozenset({
        "TEACHER_CONFIRMED", "COLLEGE_REVIEW", "APPROVED", "READY",
    })
    assert attendance.attendance_task_executable("TEACHER_CONFIRMED") is True
    assert attendance.attendance_task_executable("COLLEGE_REVIEW") is True
    assert attendance.attendance_task_executable("APPROVED") is True
    assert attendance.attendance_task_executable("READY") is True
    assert attendance.attendance_task_executable("ASSIGNED") is False
    assert attendance.attendance_task_executable("PENDING_ASSIGN") is False

    projection_source = inspect.getsource(today._teacher_schedule_in_session)
    assert "attendance_task_executable(task.status)" in projection_source
    assert 'status.notin_(["PENDING_ASSIGN", "REJECTED_BY_TEACHER", "MERGED"])' not in projection_source

    command_source = inspect.getsource(command.create_session)
    assert "public.attendance_task_executable(task.status)" in command_source
    assert "task.status or" not in command_source
