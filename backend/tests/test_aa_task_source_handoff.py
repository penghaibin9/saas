"""真实 MySQL 承接事务：保留原执行历史，独立权限、重放、冲突与审计原子性。"""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from tests.test_aa_schedule import TID, _hdr
from tests.test_aa_task_source_review import _pair, _review


@pytest.mark.parametrize("changed", ["class", "relation", "unprojected_task"])
def test_locked_teacher_authority_refreshes_objects_loaded_before_change(client, db_mode, changed):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_teacher_relation_authority as authority

    facts = _pair(client)
    with _context(facts["school"]):
        with get_sessionmaker()() as db:
            task = db.get(AaTeachingTask, int(facts["newId"]))
            clazz = db.get(AaTeachingClass, facts["newClassId"])
            relation = db.query(AaTeachingClassTeacher).filter_by(
                tenant_id=TID, teaching_class_id=clazz.id, status="ACTIVE").one()
            teacher = {"loginName": relation.teacher_key, "userId": str(relation.teacher_id)}
            if changed == "unprojected_task":
                clazz.is_deleted = True
                db.commit()
            assert authority.require_teacher(db, task, teacher)["matchedTeacherKeys"]
            with get_sessionmaker()() as other:
                if changed == "class":
                    other.get(AaTeachingClass, clazz.id).status = "ARCHIVED"
                elif changed == "relation":
                    other.get(AaTeachingClassTeacher, relation.id).teacher_key = "replacement_teacher"
                else:
                    other.get(AaTeachingTask, task.id).teacher_key = "replacement_teacher"
                other.commit()
            with pytest.raises(AppException) as denied:
                authority.require_teacher(db, task, teacher, lock=True)
            assert denied.value.http_status == (409 if changed == "class" else 403)
            if changed == "class":
                assert clazz.status == "ARCHIVED"
            elif changed == "relation":
                assert relation.teacher_key == "replacement_teacher"
            else:
                assert task.teacher_key == "replacement_teacher"
            db.rollback()


def _setup(client):
    from app.db.session import get_sessionmaker
    from app.models import Role, RolePermission
    from tests.support_academic_review_identity import _ensure_permission
    facts = _pair(client)
    with get_sessionmaker()() as db:
        for role_code in ("SCHOOL_ADMIN", "COLLEGE_ADMIN"):
            role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == role_code).one()
            permission = _ensure_permission(db, "academicAffairs.teachingTask.confirm")
            if not db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
                db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
        db.commit()
    facts["school"], facts["college"] = _hdr(client, "school_admin01"), _hdr(client, "college_admin01")
    return facts


@contextmanager
def _context(headers):
    from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
    from app.core.security import decode_token
    previous_tenant, previous_user = get_tenant(), get_current_user_ctx()
    user = decode_token(headers["Authorization"].removeprefix("Bearer "))
    set_tenant(TID); set_current_user(user)
    try:
        yield user
    finally:
        set_tenant(previous_tenant); set_current_user(previous_user)


def _body(client, facts, **changes):
    response = _review(client, facts)
    assert response.status_code == 200, response.text
    values = dict(successorTaskId=facts["newId"], reason="校级责任人核实同一课程由原任务继续执行",
        expectedSourceFingerprint=response.json()["data"]["sourceFingerprint"],
        idempotencyKey="isolated-task-source-handoff-001")
    values.update(changes)
    return SimpleNamespace(**values)


def _confirm(facts, body, *, headers=None, execution_id=None):
    from app.modules.academic_affairs.services.academic_affairs_task_source_handoff_service import confirm_source_handoff
    with _context(headers or facts["school"]) as user:
        return confirm_source_handoff(execution_id or facts["oldId"], body, user)


def _task_snapshot(db, facts):
    from app.models import AaTeachingTask
    return [(row.id, row.version, row.status, row.source_program_course_id, row.formation_mode,
        row.teacher_id, row.teacher_key, row.total_hours, row.start_week, row.end_week)
        for row in db.query(AaTeachingTask).filter(AaTeachingTask.id.in_(
            [int(facts["oldId"]), int(facts["newId"])])).order_by(AaTeachingTask.id).all()]


def test_confirm_persists_one_relation_and_audit_then_replays_without_task_rewrite(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskSourceHandoff, AffairsAuditTrail
    from app.modules.academic_affairs.services.academic_affairs_task_execution_authority import require_independent_task
    from app.core.exceptions import AppException
    facts = _setup(client); body = _body(client, facts)
    with get_sessionmaker()() as db:
        before = _task_snapshot(db, facts)
    first, again = _confirm(facts, body), _confirm(facts, body)
    assert first == again
    assert first["executionTaskId"] == facts["oldId"] and first["successorTaskId"] == facts["newId"]
    with get_sessionmaker()() as db:
        assert _task_snapshot(db, facts) == before
        assert db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID).count() == 1
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type="AA_TASK_SOURCE_HANDOFF").count() == 1
        with _context(facts["school"]):
            assert require_independent_task(db, facts["oldId"]).id == int(facts["oldId"])
            with pytest.raises(AppException) as blocked:
                require_independent_task(db, facts["newId"])
            assert blocked.value.http_status == 409
        db.rollback()


@pytest.mark.parametrize("change", ["fingerprint", "unknown", "consumed_history", "retake_history", "college", "foreign_tenant", "direction"])
def test_invalid_or_stale_confirmation_never_writes_relation(client, db_mode, change):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaProgramCourse, AaRetakeApply, AaScheduleBatch, AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch, AaTeachingTaskSourceHandoff
    facts = _setup(client); body = _body(client, facts)
    with get_sessionmaker()() as db:
        new = db.get(AaTeachingTask, int(facts["newId"]))
        if change == "fingerprint": body.expectedSourceFingerprint = "0" * 64
        elif change == "unknown":
            new.formation_mode = db.get(AaProgramCourse, new.source_program_course_id).formation_mode = None
        elif change == "consumed_history":
            schedule = AaScheduleBatch(tenant_id=TID, term_id=facts["termId"], batch_name="曾消费后继", status="DRAFT")
            db.add(schedule); db.flush()
            db.add(AaScheduleItem(tenant_id=TID, batch_id=schedule.id, task_id=new.id, weekday=2,
                slot_no=1, start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE", is_deleted=True))
        elif change == "retake_history":
            db.add(AaRetakeApply(tenant_id=TID, student_id=711, teaching_task_ref=new.id,
                course_id=new.course_id, status="ENROLLED", is_deleted=True))
        elif change == "college": db.get(AaTeachingTaskBatch, new.batch_id).college_id = int(facts["tasks"][1]["collegeId"])
        elif change == "foreign_tenant": new.tenant_id = TID + 1
        elif change == "direction": body.successorTaskId = facts["oldId"]
        db.commit()
    with pytest.raises(AppException) as blocked:
        _confirm(facts, body, execution_id=facts["newId"] if change == "direction" else None)
    assert blocked.value.http_status in (404, 409)
    with get_sessionmaker()() as db:
        assert db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID).count() == 0


def test_college_with_confirm_permission_is_not_school_responsible_actor(client, db_mode):
    from app.core.exceptions import AppException
    facts = _setup(client); body = _body(client, facts)
    with pytest.raises(AppException) as blocked:
        _confirm(facts, body, headers=facts["college"])
    assert blocked.value.http_status == 403


def test_same_request_key_different_content_does_not_overwrite(client, db_mode):
    from app.core.exceptions import AppException
    facts = _setup(client); body = _body(client, facts)
    before = _confirm(facts, body)
    body.reason = "换一种承接内容不得覆盖已确认历史"
    with pytest.raises(AppException) as blocked:
        _confirm(facts, body)
    assert blocked.value.http_status == 409
    body.reason = "校级责任人核实同一课程由原任务继续执行"
    assert _confirm(facts, body) == before


def test_audit_failure_rolls_back_handoff_and_task_history(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskSourceHandoff
    from app.modules.academic_affairs.services import academic_affairs_task_source_handoff_service as service
    facts = _setup(client); body = _body(client, facts)
    with get_sessionmaker()() as db:
        before = _task_snapshot(db, facts)
    def fail_audit(*args):
        raise RuntimeError("isolated required audit failure")
    monkeypatch.setattr(service, "_write_audit", fail_audit)
    with pytest.raises(RuntimeError, match="required audit"):
        _confirm(facts, body)
    with get_sessionmaker()() as db:
        assert _task_snapshot(db, facts) == before
        assert db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID).count() == 0


def test_existing_execution_anchor_cannot_become_a_successor(client, db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramCourse, AaTeachingTask, AaTeachingTaskSourceHandoff
    facts = _setup(client); body = _body(client, facts)
    original_receipt = _confirm(facts, body)
    with get_sessionmaker()() as db:
        original = db.get(AaTeachingTask, int(facts["oldId"]))
        original_source = db.get(AaProgramCourse, original.source_program_course_id)
        original_program = db.get(AaProgram, original_source.program_id)
        ancestor_program = AaProgram(tenant_id=TID, major_id=original_program.major_id,
            grade_year=original_program.grade_year, program_name="更早隔离方案", series_key=original_program.series_key,
            version=0, status="PUBLISHED")
        db.add(ancestor_program); db.flush()
        original_program.prev_version_id = ancestor_program.id
        source = AaProgramCourse(tenant_id=TID, program_id=ancestor_program.id, course_id=original.course_id,
            course_name=original.course_name, open_term_no=1, formation_mode="ADMIN_FIXED", credit_snapshot=1)
        db.add(source); db.flush()
        ancestor = AaTeachingTask(tenant_id=TID, batch_id=original.batch_id, source_program_course_id=source.id,
            course_id=original.course_id, class_id=original.class_id, formation_mode="ADMIN_FIXED", status="READY",
            teacher_key=original.teacher_key, weekly_hours=original.weekly_hours, total_hours=original.total_hours,
            start_week=1, end_week=18)
        db.add(ancestor); db.flush()
        ancestor_id = ancestor.id
        db.commit()
    second = SimpleNamespace(successorTaskId=facts["oldId"], reason="禁止将既有执行锚点改为后继",
        expectedSourceFingerprint="a" * 64, idempotencyKey="isolated-invalid-anchor-chain")
    with pytest.raises(AppException, match="已有执行链") as blocked:
        _confirm(facts, second, execution_id=ancestor_id)
    assert blocked.value.http_status == 409
    with get_sessionmaker()() as db:
        assert db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID).count() == 1
    assert _confirm(facts, body) == original_receipt


def test_competing_confirmations_wait_for_shared_term_then_replay_once(client, db_mode):
    """两个真实写事务竞争同一来源，第二次等待共同锁后只回读首次结果。"""
    import re
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, local
    from sqlalchemy import event
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaTeachingTaskSourceHandoff, AffairsAuditTrail

    facts = _setup(client); body = _body(client, facts)
    held, waiting = Event(), Event()
    worker = local()
    def before_sql(conn, cursor, statement, parameters, context, executemany):
        if (getattr(worker, "role", None) == "second" and "FOR UPDATE" in statement.upper()
                and re.search(r"\bFROM\s+t_aa_term\b", statement, re.I)):
            waiting.set()
    def after_sql(conn, cursor, statement, parameters, context, executemany):
        if (getattr(worker, "role", None) == "first" and not held.is_set()
                and "FOR UPDATE" in statement.upper()
                and re.search(r"\bFROM\s+t_aa_teaching_task\b", statement, re.I)):
            held.set()
            assert waiting.wait(10), "第二个确认未进入共同学期锁等待窗口"
    def confirm(role):
        worker.role = role
        return _confirm(facts, body)
    engine = get_engine()
    event.listen(engine, "before_cursor_execute", before_sql)
    event.listen(engine, "after_cursor_execute", after_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(confirm, "first")
            assert held.wait(10), "第一个确认未取得共同任务锁"
            second = pool.submit(confirm, "second")
            receipt = first.result(timeout=25)
            replay = second.result(timeout=25)
    finally:
        event.remove(engine, "before_cursor_execute", before_sql)
        event.remove(engine, "after_cursor_execute", after_sql)
    assert waiting.is_set() and receipt == replay
    with get_sessionmaker()() as db:
        assert db.query(AaTeachingTaskSourceHandoff).filter_by(tenant_id=TID).count() == 1
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type="AA_TASK_SOURCE_HANDOFF").count() == 1


def test_reverse_review_action_confirms_same_direction_and_reads_back_receipt(client, db_mode):
    facts = _setup(client)
    forward = _review(client, facts).json()["data"]
    response = client.get(f"/api/v1/academic-affairs/teaching-tasks/{facts['newId']}/source-review",
        headers=facts["school"], params={"otherTaskId": facts["oldId"]})
    assert response.status_code == 200, response.text
    reverse = response.json()["data"]
    assert reverse["taskIds"] == [facts["newId"], facts["oldId"]]
    assert forward["handoffAction"] == reverse["handoffAction"]
    assert reverse["handoffAction"]["allowed"] is True
    assert reverse["sourceFingerprint"] == forward["sourceFingerprint"]
    college = _review(client, facts, headers=facts["college"]).json()["data"]
    assert college["handoffAction"]["allowed"] is False and college["confirmedHandoff"] is None
    body = _body(client, facts, expectedSourceFingerprint=reverse["handoffAction"]["expectedSourceFingerprint"])
    receipt = _confirm(facts, body)
    readback = _review(client, facts).json()["data"]
    assert readback["confirmedHandoff"] == receipt
    assert readback["handoffAction"]["allowed"] is False
