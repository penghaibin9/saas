from __future__ import annotations

from datetime import datetime

import pytest

TID = 1000000000000007100


def _ctx():
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "u_CW1-T1",
        "tenantId": str(TID),
        "realName": "C-W1教师",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "activeContextId": "ctx-cw1-change",
        "loginName": "CW1-T1",
    })


def _session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


def _seed_base(db):
    from app.models import (
        AaCourse,
        AaScheduleBatch,
        AaScheduleItem,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
    )
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth

    term = AaTerm(
        tenant_id=TID,
        year_code="2026-2027",
        term_no=1,
        term_name="C-W1调课课次学期",
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 7, 5),
        teaching_weeks=18,
        is_current=True,
        status="PUBLISHED",
    )
    db.add(term); db.flush()
    course = AaCourse(
        tenant_id=TID,
        course_code="CW1-CHG-C001",
        course_name="调课课次测试课",
        credit=2,
        status="ENABLED",
    )
    db.add(course); db.flush()
    task_batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=11,
        batch_name="C-W1调课教学任务批次",
        status="APPROVED",
    )
    db.add(task_batch); db.flush()
    task = AaTeachingTask(
        tenant_id=TID,
        batch_id=task_batch.id,
        course_id=course.id,
        course_code=course.course_code,
        course_name=course.course_name,
        teacher_key="CW1-T1",
        teacher_name="C-W1教师",
        class_id=101,
        status="APPROVED",
        weekly_hours=2,
        total_hours=36,
        start_week=1,
        end_week=18,
    )
    db.add(task); db.flush()
    schedule_batch = AaScheduleBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=11,
        batch_name="C-W1调课正式课表",
        status="PUBLISHED",
    )
    db.add(schedule_batch); db.flush()
    origin = AaScheduleItem(
        tenant_id=TID,
        batch_id=schedule_batch.id,
        task_id=task.id,
        course_id=course.id,
        course_name=course.course_name,
        teacher_key=task.teacher_key,
        teacher_name=task.teacher_name,
        class_id=101,
        weekday=1,
        slot_no=2,
        start_week=1,
        end_week=18,
        week_parity="ALL",
        status="EFFECTIVE",
    )
    db.add(origin); db.flush()
    head = truth.lock_scope_head(db, term.id, "COLLEGE", 11)
    head.active_batch_id = schedule_batch.id
    head.version = 4
    head.published_at = datetime(2026, 2, 20, 8, 0, 0)
    db.flush()
    return term, task_batch, task, schedule_batch, origin


def _link_change(db, *, term, task, schedule_batch, origin, change_type, status):
    from app.models import AaScheduleChange, AaScheduleItem

    target_weekday = 2 if change_type == "ADJUST" else 3
    target_slot = 3 if change_type == "ADJUST" else 4
    change = AaScheduleChange(
        tenant_id=TID,
        term_id=term.id,
        batch_id=schedule_batch.id,
        origin_item_id=origin.id,
        task_id=task.id,
        change_type=change_type,
        course_name=task.course_name,
        class_id=101,
        class_name="测试班",
        teacher_key=task.teacher_key,
        teacher_name=task.teacher_name,
        origin_weekday=origin.weekday,
        origin_slot_no=origin.slot_no,
        origin_start_week=origin.start_week,
        origin_end_week=origin.end_week,
        origin_week_parity=origin.week_parity,
        target_weekday=target_weekday,
        target_slot_no=target_slot,
        target_start_week=1,
        target_end_week=18,
        target_week_parity="ALL",
        reason="C-W1调课正式课次验证",
        status=status,
        applied_at=(datetime(2026, 3, 1, 9, 0, 0) if status == "APPLIED" else None),
    )
    db.add(change); db.flush()
    new_item = AaScheduleItem(
        tenant_id=TID,
        batch_id=schedule_batch.id,
        task_id=task.id,
        course_id=task.course_id,
        course_name=task.course_name,
        teacher_key=task.teacher_key,
        teacher_name=task.teacher_name,
        class_id=101,
        weekday=target_weekday,
        slot_no=target_slot,
        start_week=1,
        end_week=18,
        week_parity="ALL",
        change_id=change.id,
        status="EFFECTIVE",
    )
    db.add(new_item); db.flush()
    change.new_item_id = new_item.id
    if change_type == "ADJUST" and status == "APPLIED":
        origin.status = "CHANGED"
    db.flush()
    return change, new_item


def _resolve(db, term, task_batch, task, *, day, slot, lock=True):
    from app.modules.academic_affairs.services import academic_affairs_attendance_occurrence_consumer as consumer
    return consumer.resolve_formal_occurrence(
        db,
        task,
        task_batch,
        term,
        session_date=day,
        slot_no=slot,
        lock=lock,
    )


def test_unapplied_linked_effective_item_fails_closed(db_mode):
    from app.core.exceptions import AppException

    _ctx()
    db = _session()
    term, task_batch, task, batch, origin = _seed_base(db)
    _change, _new_item = _link_change(
        db,
        term=term,
        task=task,
        schedule_batch=batch,
        origin=origin,
        change_type="ADJUST",
        status="APPROVED",
    )
    db.commit()
    with pytest.raises(AppException) as exc:
        _resolve(db, term, task_batch, task, day="2026-03-03", slot=3)
    assert exc.value.http_status == 409
    assert "APPLIED" in exc.value.message or "生效" in exc.value.message
    db.close()


def test_applied_adjust_new_occurrence_succeeds_and_old_is_rejected(db_mode):
    from app.core.exceptions import AppException

    _ctx()
    db = _session()
    term, task_batch, task, batch, origin = _seed_base(db)
    change, new_item = _link_change(
        db,
        term=term,
        task=task,
        schedule_batch=batch,
        origin=origin,
        change_type="ADJUST",
        status="APPLIED",
    )
    db.commit()

    result = _resolve(db, term, task_batch, task, day="2026-03-03", slot=3)
    assert result["scheduleItemId"] == str(new_item.id)
    assert result["changeId"] == str(change.id)
    assert result["changeType"] == "ADJUST"
    assert result["changeAppliedAt"]

    with pytest.raises(AppException):
        _resolve(db, term, task_batch, task, day="2026-03-02", slot=2)
    db.close()


def test_applied_makeup_additional_occurrence_succeeds(db_mode):
    _ctx()
    db = _session()
    term, task_batch, task, batch, origin = _seed_base(db)
    change, new_item = _link_change(
        db,
        term=term,
        task=task,
        schedule_batch=batch,
        origin=origin,
        change_type="MAKEUP",
        status="APPLIED",
    )
    db.commit()

    result = _resolve(db, term, task_batch, task, day="2026-03-04", slot=4)
    assert result["scheduleItemId"] == str(new_item.id)
    assert result["changeId"] == str(change.id)
    assert result["changeType"] == "MAKEUP"

    original = _resolve(db, term, task_batch, task, day="2026-03-02", slot=2)
    assert original["scheduleItemId"] == str(origin.id)
    assert original["changeId"] is None
    db.close()
