from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import pytest

TID = 1000000000000007000


def _ctx():
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "u_CW1-T1",
        "tenantId": str(TID),
        "realName": "C-W1教师",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "activeContextId": "ctx-cw1",
        "loginName": "CW1-T1",
    })


def _session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


@contextmanager
def _service_session():
    db = _session()
    try:
        yield db
    finally:
        db.close()


def _seed(db, *, activate: bool):
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
        term_name="C-W1正式课次学期",
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 7, 5),
        teaching_weeks=18,
        is_current=True,
        status="PUBLISHED",
    )
    db.add(term)
    db.flush()
    course = AaCourse(
        tenant_id=TID,
        course_code="CW1-C001",
        course_name="正式课次测试课",
        credit=2,
        status="ENABLED",
    )
    db.add(course)
    db.flush()
    task_batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=11,
        batch_name="C-W1教学任务批次",
        status="APPROVED",
    )
    db.add(task_batch)
    db.flush()
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
    db.add(task)
    db.flush()
    schedule_batch = AaScheduleBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=11,
        batch_name="C-W1正式课表",
        status="PUBLISHED",
    )
    db.add(schedule_batch)
    db.flush()
    item = AaScheduleItem(
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
    db.add(item)
    db.flush()
    if activate:
        head = truth.lock_scope_head(db, term.id, "COLLEGE", 11)
        head.active_batch_id = schedule_batch.id
        head.version = 3
        head.published_at = datetime(2026, 2, 20, 8, 0, 0)
        db.flush()
    return term, task_batch, task, schedule_batch, item


def _fake_roster():
    return {
        "source": "SELECTION_LOCKED",
        "sourceRefId": "selection-cw1",
        "rosterVersionId": "rv-cw1",
        "rosterVersionNo": 1,
        "items": [{
            "studentId": "501",
            "studentNo": "S501",
            "realName": "测试学生",
            "classId": "101",
        }],
    }


def _patch_roster(monkeypatch, service, calls):
    def resolve(_db, _task_id):
        calls["roster"] += 1
        return _fake_roster()

    monkeypatch.setattr(service, "resolve_versioned_roster", resolve)
    monkeypatch.setattr(service, "freeze_consumer_snapshot", lambda *_args, **_kwargs: {
        "rosterVersionId": "rv-cw1",
        "rosterVersionNo": 1,
        "rosterSource": "SELECTION_LOCKED",
    })
    monkeypatch.setattr(service, "_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "session", _service_session)


def _user():
    return {
        "userType": "STAFF",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "loginName": "CW1-T1",
        "userId": "u_CW1-T1",
    }


def test_create_session_rejects_no_scope_head_before_roster(monkeypatch, db_mode):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    _ctx()
    db = _session()
    _term, _task_batch, task, _batch, _item = _seed(db, activate=False)
    task_id = int(task.id)
    db.commit()
    db.close()

    calls = {"roster": 0}
    _patch_roster(monkeypatch, service, calls)
    with pytest.raises(AppException) as exc:
        service.create_session(_user(), {
            "teachingTaskId": task_id,
            "classId": 101,
            "sessionDate": "2026-03-02",
            "slotNo": 2,
            "sessionType": "常规",
        })
    assert exc.value.http_status == 409
    assert "正式课表" in exc.value.message
    assert calls["roster"] == 0


def test_college_active_occurrence_resolves(db_mode):
    from app.modules.academic_affairs.services import academic_affairs_attendance_occurrence_consumer as consumer

    _ctx()
    db = _session()
    term, task_batch, task, batch, item = _seed(db, activate=True)
    db.commit()
    result = consumer.resolve_formal_occurrence(
        db,
        task,
        task_batch,
        term,
        session_date="2026-03-02",
        slot_no=2,
    )
    assert result["activeBatchId"] == str(batch.id)
    assert result["scheduleItemId"] == str(item.id)
    assert result["teachingTaskId"] == str(task.id)
    assert result["scopeType"] == "COLLEGE"
    assert result["scopeHeadVersion"] == 3
    assert result["weekNo"] == 1
    assert result["weekday"] == 1
    db.close()


def test_wrong_slot_and_even_week_are_rejected(db_mode):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_occurrence_consumer as consumer

    _ctx()
    db = _session()
    term, task_batch, task, _batch, item = _seed(db, activate=True)
    item.week_parity = "ODD"
    db.commit()
    with pytest.raises(AppException):
        consumer.resolve_formal_occurrence(
            db, task, task_batch, term,
            session_date="2026-03-02", slot_no=3,
        )
    with pytest.raises(AppException):
        consumer.resolve_formal_occurrence(
            db, task, task_batch, term,
            session_date="2026-03-09", slot_no=2,
        )
    db.close()
