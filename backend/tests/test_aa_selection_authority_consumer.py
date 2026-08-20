from __future__ import annotations

import pytest

TID = 1000000000000000001


def _tenant_ctx():
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "u_w2", "tenantId": str(TID), "realName": "W2教务",
        "currentRoleCode": "ACADEMIC_ADMIN", "activeContextId": "ctx-w2",
    })


def _session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()


def _task(db, *, term_id=1, college_id=11):
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch
    course = AaCourse(
        tenant_id=TID, course_code="W2-C001", course_name="W2正式课表课",
        credit=2, status="ENABLED",
    )
    db.add(course); db.flush()
    task_batch = AaTeachingTaskBatch(
        tenant_id=TID, term_id=int(term_id), college_id=college_id,
        batch_name="W2教学任务批次", status="APPROVED",
    )
    db.add(task_batch); db.flush()
    task = AaTeachingTask(
        tenant_id=TID, batch_id=task_batch.id, course_id=course.id,
        course_code=course.course_code, course_name=course.course_name,
        teacher_key="W2-T1", teacher_name="W2教师", status="READY",
        weekly_hours=2, total_hours=36, start_week=1, end_week=18,
    )
    db.add(task); db.flush()
    return course, task


def _schedule(db, course, task, *, term_id=1, college_id=None, status="PUBLISHED", name="W2课表"):
    from app.models import AaScheduleBatch, AaScheduleItem
    batch = AaScheduleBatch(
        tenant_id=TID, term_id=int(term_id), college_id=college_id,
        batch_name=name, status=status,
    )
    db.add(batch); db.flush()
    item = AaScheduleItem(
        tenant_id=TID, batch_id=batch.id, task_id=task.id, course_id=course.id,
        course_name=course.course_name, teacher_key=task.teacher_key,
        teacher_name=task.teacher_name, weekday=1, slot_no=2,
        start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE",
    )
    db.add(item); db.flush()
    return batch


def _activate(db, truth, batch, scope_type, scope_id):
    head = truth.lock_scope_head(db, int(batch.term_id), scope_type, scope_id)
    head.active_batch_id = int(batch.id)
    head.version = max(1, int(head.version or 0))
    db.flush()


def test_passed_courses_are_effective_grade_projection(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_selection_authority_consumer as consumer
    monkeypatch.setattr(consumer.grade_service, "transcript", lambda student_id, user: {
        "policyCode": "LATEST_FORMAL_SOURCE_V1",
        "items": [
            {"courseCode": " c001 ", "courseName": "课程甲", "passStatus": "PASSED"},
            {"courseCode": "C002", "courseName": "课程乙", "passStatus": "FAILED"},
            {"courseCode": "C003", "courseName": "课程丙", "passStatus": "PASSED"},
        ],
    })
    assert consumer.passed_course_codes(7, {"currentRoleCode": "STUDENT"}) == {"C001", "C003"}
    assert consumer.passed_course_names(7, {"currentRoleCode": "STUDENT"}) == {"课程甲", "课程丙"}


def test_no_scope_head_means_no_historical_fallback(db_mode):
    _tenant_ctx()
    from app.modules.academic_affairs.services import academic_affairs_selection_authority_consumer as consumer
    db = _session()
    course, task = _task(db)
    _schedule(db, course, task, college_id=11, status="SUPERSEDED", name="历史课表")
    db.commit()
    assert consumer.task_slots(db, task.id) == []
    db.close()


def test_college_active_scope_is_counted(db_mode):
    _tenant_ctx()
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth
    from app.modules.academic_affairs.services import academic_affairs_selection_authority_consumer as consumer
    db = _session()
    course, task = _task(db, college_id=11)
    batch = _schedule(db, course, task, college_id=11)
    _activate(db, truth, batch, "COLLEGE", 11)
    db.commit()
    assert consumer.task_slots(db, task.id) == [(1, 2, 1, 18, "ALL")]
    db.close()


def test_school_active_scope_can_carry_college_task(db_mode):
    _tenant_ctx()
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth
    from app.modules.academic_affairs.services import academic_affairs_selection_authority_consumer as consumer
    db = _session()
    course, task = _task(db, college_id=11)
    batch = _schedule(db, course, task, college_id=None)
    _activate(db, truth, batch, "SCHOOL", 0)
    db.commit()
    assert consumer.task_slots(db, task.id) == [(1, 2, 1, 18, "ALL")]
    db.close()


def test_same_task_in_school_and_college_active_heads_fails_closed(db_mode):
    _tenant_ctx()
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth
    from app.modules.academic_affairs.services import academic_affairs_selection_authority_consumer as consumer
    db = _session()
    course, task = _task(db, college_id=11)
    school = _schedule(db, course, task, college_id=None, name="全校正式课表")
    college = _schedule(db, course, task, college_id=11, name="学院正式课表")
    _activate(db, truth, school, "SCHOOL", 0)
    _activate(db, truth, college, "COLLEGE", 11)
    db.commit()
    with pytest.raises(AppException) as exc:
        consumer.task_slots(db, task.id)
    assert getattr(exc.value, "http_status", None) == 409
    assert "多个当前正式课表范围" in str(exc.value)
    db.close()
