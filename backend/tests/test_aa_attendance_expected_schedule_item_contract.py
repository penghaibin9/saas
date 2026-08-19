from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

TID = 1000000000000007400
ROOT = Path(__file__).resolve().parents[2]


def _ctx():
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "u_CW1-T1",
        "tenantId": str(TID),
        "realName": "C-W1教师",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "activeContextId": "ctx-cw1-expected-item",
        "loginName": "CW1-T1",
    })


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
    )
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth

    term = AaTerm(
        tenant_id=TID,
        year_code="2026-2027",
        term_no=1,
        term_name="C-W1课次身份学期",
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 7, 5),
        teaching_weeks=18,
        is_current=True,
        status="PUBLISHED",
    )
    db.add(term); db.flush()
    course = AaCourse(
        tenant_id=TID,
        course_code="CW1-ID-C001",
        course_name="课次身份测试课",
        credit=2,
        status="ENABLED",
    )
    db.add(course); db.flush()
    task_batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=11,
        batch_name="C-W1课次身份教学任务批次",
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
        batch_name="C-W1课次身份正式课表",
        status="PUBLISHED",
    )
    db.add(schedule_batch); db.flush()
    monday = AaScheduleItem(
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
    wednesday = AaScheduleItem(
        tenant_id=TID,
        batch_id=schedule_batch.id,
        task_id=task.id,
        course_id=course.id,
        course_name=course.course_name,
        teacher_key=task.teacher_key,
        teacher_name=task.teacher_name,
        class_id=101,
        weekday=3,
        slot_no=2,
        start_week=1,
        end_week=18,
        week_parity="ALL",
        status="EFFECTIVE",
    )
    db.add_all([monday, wednesday]); db.flush()
    head = truth.lock_scope_head(db, term.id, "COLLEGE", 11)
    head.active_batch_id = schedule_batch.id
    head.version = 8
    head.published_at = datetime(2026, 2, 20, 8, 0, 0)
    db.flush()
    return term, task_batch, task, monday, wednesday


def test_expected_schedule_item_must_match_realtime_resolved_occurrence(db_mode):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_occurrence_consumer as consumer

    _ctx()
    db = _session()
    term, task_batch, task, monday, wednesday = _seed(db)
    db.commit()

    result = consumer.resolve_formal_occurrence(
        db,
        task,
        task_batch,
        term,
        session_date="2026-03-02",
        slot_no=2,
        expected_schedule_item_id=str(monday.id),
    )
    assert result["scheduleItemId"] == str(monday.id)

    with pytest.raises(AppException) as exc:
        consumer.resolve_formal_occurrence(
            db,
            task,
            task_batch,
            term,
            session_date="2026-03-02",
            slot_no=2,
            expected_schedule_item_id=str(wednesday.id),
        )
    assert exc.value.http_status == 409
    assert "课次已变化" in exc.value.message
    db.close()


def test_invalid_expected_schedule_item_identity_is_rejected(db_mode):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_occurrence_consumer as consumer

    _ctx()
    db = _session()
    term, task_batch, task, _monday, _wednesday = _seed(db)
    db.commit()
    with pytest.raises(AppException) as exc:
        consumer.resolve_formal_occurrence(
            db,
            task,
            task_batch,
            term,
            session_date="2026-03-02",
            slot_no=2,
            expected_schedule_item_id="not-an-id",
        )
    assert "scheduleItemId" in exc.value.message
    db.close()


def test_attendance_command_forwards_client_schedule_item_identity():
    source = (
        ROOT
        / "backend/app/modules/academic_affairs/services/academic_affairs_attendance_teacher_relation_guard.py"
    ).read_text(encoding="utf-8")
    assert 'expected_schedule_item_id=body.get("scheduleItemId")' in source
