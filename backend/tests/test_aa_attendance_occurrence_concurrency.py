from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

TID = 1000000000000007200


def _ctx():
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "u_CW1-T1",
        "tenantId": str(TID),
        "realName": "C-W1教师",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "activeContextId": "ctx-cw1-concurrency",
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
    return get_sessionmaker()()


def _seed():
    _ctx()
    from app.models import (
        AaCourse,
        AaScheduleBatch,
        AaScheduleItem,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
    )
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth

    db = _session()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code="2026-2027",
            term_no=1,
            term_name="C-W1考勤并发学期",
            start_date=datetime(2026, 3, 2),
            end_date=datetime(2026, 7, 5),
            teaching_weeks=18,
            is_current=True,
            status="PUBLISHED",
        )
        db.add(term); db.flush()
        course = AaCourse(
            tenant_id=TID,
            course_code="CW1-CON-C001",
            course_name="考勤并发测试课",
            credit=2,
            status="ENABLED",
        )
        db.add(course); db.flush()
        task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            college_id=11,
            batch_name="C-W1考勤并发教学任务批次",
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
            batch_name="C-W1考勤并发正式课表",
            status="PUBLISHED",
        )
        db.add(schedule_batch); db.flush()
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
        db.add(item); db.flush()
        head = truth.lock_scope_head(db, term.id, "COLLEGE", 11)
        head.active_batch_id = schedule_batch.id
        head.version = 5
        head.published_at = datetime(2026, 2, 20, 8, 0, 0)
        db.commit()
        return int(task.id)
    finally:
        db.close()


def _fake_roster():
    return {
        "source": "SELECTION_LOCKED",
        "sourceRefId": "selection-cw1-concurrency",
        "rosterVersionId": "rv-cw1-concurrency",
        "rosterVersionNo": 1,
        "items": [{
            "studentId": "501",
            "studentNo": "S501",
            "realName": "并发测试学生",
            "classId": "101",
        }],
    }


def _install_fast_roster(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service
    monkeypatch.setattr(service, "resolve_versioned_roster", lambda _db, _task_id: _fake_roster())
    monkeypatch.setattr(service, "freeze_consumer_snapshot", lambda *_args, **_kwargs: {
        "rosterVersionId": "rv-cw1-concurrency",
        "rosterVersionNo": 1,
        "rosterSource": "SELECTION_LOCKED",
    })
    monkeypatch.setattr(service, "_audit", lambda *_args, **_kwargs: None)
    return service


def _body(task_id):
    return {
        "teachingTaskId": task_id,
        "classId": 101,
        "sessionDate": "2026-03-02",
        "slotNo": 2,
        "sessionType": "常规",
    }


@pytest.mark.usefixtures("db_mode")
def test_same_formal_occurrence_concurrent_create_only_one_wins(monkeypatch):
    service = _install_fast_roster(monkeypatch)
    task_id = _seed()
    barrier = Barrier(2)

    def create_one(_index):
        _ctx()
        barrier.wait()
        try:
            result = service.create_session(_user(), _body(task_id))
            return ("ok", str(result["sessionId"]))
        except AppException as exc:
            return ("rejected", int(exc.http_status or 0), str(exc.message))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create_one, (1, 2)))

    successes = sum(result[0] == "ok" for result in results)
    rejects = [result for result in results if result[0] == "rejected"]
    assert successes == 1, f"EXPECTED_ONE_WINNER actual_successes={successes} results={results}"
    assert len(rejects) == 1, results
    assert rejects[0][1] == 409
    assert "已创建" in rejects[0][2]

    from app.models import AaAttendanceSession
    db = _session()
    try:
        rows = db.query(AaAttendanceSession).filter(
            AaAttendanceSession.tenant_id == TID,
            AaAttendanceSession.class_id == 101,
            AaAttendanceSession.teacher_key == "CW1-T1",
            AaAttendanceSession.session_date == "2026-03-02",
            AaAttendanceSession.slot_no == 2,
            AaAttendanceSession.is_deleted.is_(False),
        ).all()
        assert len(rows) == 1
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_admin_special_same_coordinate_does_not_block_formal_occurrence(monkeypatch):
    service = _install_fast_roster(monkeypatch)
    task_id = _seed()
    from app.models import AaAttendanceSession

    db = _session()
    try:
        db.add(AaAttendanceSession(
            tenant_id=TID,
            class_id=101,
            course_name="管理员特殊补录",
            term_code="2026-2027-1",
            teacher_key="CW1-T1",
            session_date="2026-03-02",
            slot_no=2,
            session_type="ADMIN_SPECIAL",
            roster_json="[]",
            total_count=0,
            present_count=0,
            absent_count=0,
            status="DRAFT",
        ))
        db.commit()
    finally:
        db.close()

    _ctx()
    result = service.create_session(_user(), _body(task_id))
    assert result["sourceType"] == "FORMAL_TEACHING"

    db = _session()
    try:
        rows = db.query(AaAttendanceSession).filter(
            AaAttendanceSession.tenant_id == TID,
            AaAttendanceSession.class_id == 101,
            AaAttendanceSession.session_date == "2026-03-02",
            AaAttendanceSession.slot_no == 2,
            AaAttendanceSession.is_deleted.is_(False),
        ).all()
        assert len(rows) == 2
        assert sorted(str(row.session_type or "") for row in rows) == ["ADMIN_SPECIAL", "常规"]
    finally:
        db.close()
