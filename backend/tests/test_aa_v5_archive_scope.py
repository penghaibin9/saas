"""学院归档仅消费本院事实；整校核查不能伪装成本院已通过。"""
from datetime import datetime
from types import SimpleNamespace as Row
from unittest.mock import MagicMock

import pytest

from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy
from app.modules.academic_affairs.services import academic_affairs_archive_operational_policy as operational
from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as semantic
from app.modules.academic_affairs.services import academic_affairs_archive_service as public


def test_college_school_coordination_is_explicitly_unchecked_not_passed():
    waiting = policy.college_school_result("EXAM", 2, 0, "", "整批封存由学校核验")
    assert waiting["result"] == "UNKNOWN" and not waiting["present"]
    assert waiting["evidence"][0]["schoolCheckPerformed"] is False
    blocked = policy.college_school_result("EXAM", 2, 1, "本院异常未闭环", "整批封存由学校核验")
    assert blocked["result"] == "BLOCKED" and blocked["recordCount"] == 2
    assert "本院异常" in blocked["summary"]


def test_college_domain_dispatch_never_runs_unscoped_school_checks(monkeypatch):
    monkeypatch.setattr(policy, "_tid", lambda: 1)
    global_check = MagicMock(side_effect=AssertionError("不能执行全校查询再删返回结果"))
    monkeypatch.setattr(policy._core, "_evaluate_domains", global_check)
    monkeypatch.setattr(policy, "policy_snapshot_debt", global_check)
    calls = []
    def scoped(*args, **kwargs):
        scope = kwargs.get("college_ids", args[-1])
        assert scope == {12}
        calls.append(scope)
        return {"result": "PASS", "present": True, "recordCount": 1, "blockingCount": 0, "summary": "本院核验通过"}
    for name in ("evaluate_college_registration", "evaluate_status_change", "evaluate_graduation",
                 "evaluate_college_selection", "evaluate_college_makeup", "evaluate_evaluation", "evaluate_college_textbook"):
        monkeypatch.setattr(policy, name, scoped)
    monkeypatch.setattr(policy._core, "_evaluate_student_status", scoped)
    for name in ("evaluate_program", "evaluate_teaching_task", "evaluate_schedule", "evaluate_grade"):
        monkeypatch.setattr(semantic, name, scoped)
    monkeypatch.setattr(operational, "evaluate_exam", scoped)
    monkeypatch.setattr(operational, "evaluate_schedule", scoped)
    result = public._evaluate_domains(MagicMock(), 52, "2041-2042-1", {12})
    assert len(result) == 13 and len(calls) == 14
    global_check.assert_not_called()
    assert result["GRADE"]["result"] == "UNKNOWN"
    assert result["GRADE"]["evidence"][0]["schoolCheckPerformed"] is False


def test_empty_or_noncollege_archive_scope_is_rejected_before_queries(monkeypatch):
    with pytest.raises(Exception, match="学院范围"):
        policy._evaluate_college_domains(MagicMock(), 1, "2041-2042-1", set())
    cm, db = MagicMock(), MagicMock()
    cm.__enter__.return_value = db
    monkeypatch.setattr(public._core, "session", lambda: cm)
    for ctx in (Row(scope_type="CLASS"), Row(scope_type="NONE"), Row(scope_type="COLLEGE", college_ids=set())):
        monkeypatch.setattr(public._core, "_ctx", lambda *args: ctx)
        with pytest.raises(Exception, match="已授权"):
            public.precheck({}, term_id=1)
    db.query.assert_not_called()


def test_archive_task_scope_explicitly_includes_school_public_courses(monkeypatch):
    from app.models import AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_schedule_policy as schedule
    calls = []
    def scope(db, batch, *, include_centralized_public=False):
        calls.append((batch.college_id, include_centralized_public))
        return AaTeachingTask.id > 0
    monkeypatch.setattr(schedule, "task_scope_condition", scope, raising=False)
    monkeypatch.setattr(operational, "_tid", lambda: 1)
    operational.college_task_ids(MagicMock(), {12, 34}, 52)
    assert calls == [(12, True), (34, True)]
    with pytest.raises(Exception, match="学院范围"):
        operational.college_task_ids(MagicMock(), set(), 52)


def test_college_archive_detail_never_reads_school_evidence_or_missing_count(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as responsibility
    db, cm = MagicMock(), MagicMock()
    cm.__enter__.return_value = db
    monkeypatch.setattr(public._core, "session", lambda: cm)
    ctx = Row(scope_type="COLLEGE", college_ids={12})
    monkeypatch.setattr(public._core, "_ctx", lambda *args: ctx)
    monkeypatch.setattr(public._core, "_get_batch", lambda *args: Row(id=1, status="ARCHIVED"))
    monkeypatch.setattr(public._core, "_batch_dto", lambda *args, **kwargs: {"batchId": "1", "missingCount": 99, **kwargs})
    school_items = MagicMock(side_effect=AssertionError("学院不得读取全校已存封存证据"))
    monkeypatch.setattr(public, "_items_dto", school_items)
    result = public.get_batch({}, 1)
    assert result["items"] == [] and result["missingCount"] is None
    assert result["scopeType"] == "COLLEGE" and "本院实时预检" in result["scopeNote"]
    school_items.assert_not_called()


def test_installed_archive_list_masks_school_counts_and_rejects_missing_scope(monkeypatch):
    from app.modules.academic_affairs.routers import academic_affairs_bundle
    route = next(route for route in academic_affairs_bundle.build_router().routes
                 if route.path == "/academic-affairs/archive/batches" and "GET" in route.methods)
    db, cm = MagicMock(), MagicMock()
    cm.__enter__.return_value = db
    db.scalar.return_value = 1
    db.scalars.return_value.all.return_value = [Row(id=1)]
    monkeypatch.setattr(public._core, "session", lambda: cm)
    monkeypatch.setattr(public._core, "_tid", lambda: 1)
    monkeypatch.setattr(public._core, "_batch_dto", lambda *args, **kwargs: {"batchId": "1", "missingCount": 99})
    monkeypatch.setattr(public._core, "_ctx", lambda *args: Row(scope_type="COLLEGE", college_ids={12}))
    result = route.endpoint(user={}, status=None, page=1, pageSize=20, termId=None)
    item = result["data"]["items"][0]
    assert item["missingCount"] is None and item["items"] == [] and item["scopeType"] == "COLLEGE"
    for ctx in (Row(scope_type="CLASS"), Row(scope_type="NONE"), Row(scope_type="COLLEGE", college_ids=set())):
        monkeypatch.setattr(public._core, "_ctx", lambda *args: ctx)
        db.reset_mock()
        with pytest.raises(Exception, match="已授权"):
            route.endpoint(user={}, status=None, page=1, pageSize=20, termId=None)
        db.scalars.assert_not_called()


@pytest.mark.parametrize("suffix,kwargs", [
    ("/export", {"purpose": "学校归档验收授权核验"}),
    ("/items/{category}/export", {"category": "STUDENT_STATUS", "purpose": "学校归档验收授权核验"}),
    ("/download-log", {}),
])
def test_installed_school_archive_materials_reject_college_before_loading_batch(monkeypatch, suffix, kwargs):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.routers import academic_affairs_bundle
    endpoint = next(route.endpoint for route in academic_affairs_bundle.build_router().routes
                    if route.path == "/academic-affairs/archive/batches/{bid}" + suffix and "GET" in route.methods)
    db, cm = MagicMock(), MagicMock()
    cm.__enter__.return_value = db
    monkeypatch.setattr(public._core, "session", lambda: cm)
    load = MagicMock(side_effect=RuntimeError("school-scope-accepted"))
    monkeypatch.setattr(public._core, "_get_batch", load)
    for scope_type in ("COLLEGE", "CLASS", "NONE", "SELF"):
        monkeypatch.setattr(public._core, "_ctx", lambda *args: Row(scope_type=scope_type, college_ids={12}))
        with pytest.raises(AppException) as denied:
            endpoint(bid=1, user={}, **kwargs)
        assert denied.value.code == "NO_DATA_SCOPE"
        load.assert_not_called()
        db.query.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()
    monkeypatch.setattr(public._core, "_ctx", lambda *args: Row(scope_type="TENANT_ALL"))
    with pytest.raises(RuntimeError, match="school-scope-accepted"):
        endpoint(bid=1, user={}, **kwargs)
    load.assert_called_once_with(db, 1)


def test_mysql_archive_keeps_foreign_students_tasks_changes_and_courses_out(db_mode, monkeypatch):
    """仅主控在独立MySQL库串行执行，使用真实归属SQL与正式状态。"""
    import importlib
    from app.db.session import get_sessionmaker
    from app.models import (AaTerm, StudentProfile, AaRegistrationBatch, AaRegistration,
        AaRegistrationException, AaCourse, AaTeachingTaskBatch, AaTeachingTask, AaGradeTask,
        AaScheduleBatch, AaScheduleItem, AaScheduleChange, AaExamBatch, AaExamCourse)
    from app.modules.academic_affairs.services import academic_affairs_schedule_policy as schedule
    exam = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_exam_service")
    tid = 1000000000000000001
    for module in (policy, operational, semantic, public._core, schedule, exam):
        monkeypatch.setattr(module, "_tid", lambda: tid)
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=tid, year_code="2041-2042", term_no=1, status="PUBLISHED",
            start_date=datetime(2041, 9, 1), end_date=datetime(2042, 1, 20), teaching_weeks=18)
        a = StudentProfile(tenant_id=tid, student_no="V5ARC-A", real_name="虚构甲", college_id=12)
        b = StudentProfile(tenant_id=tid, student_no="V5ARC-B", real_name="虚构乙", college_id=34)
        ca = AaCourse(tenant_id=tid, course_code="V5ARC-A", course_name="本院公共课", owner_college_id=12, category="PUBLIC_BASIC")
        cb = AaCourse(tenant_id=tid, course_code="V5ARC-B", course_name="外院课", owner_college_id=34)
        db.add_all([term, a, b, ca, cb]); db.flush()
        registration = AaRegistrationBatch(tenant_id=tid, term_id=term.id, batch_name="全校注册", status="OPEN")
        tb = AaTeachingTaskBatch(tenant_id=tid, term_id=term.id, college_id=34, batch_name="跨院任务", status="APPROVED")
        sb = AaScheduleBatch(tenant_id=tid, term_id=term.id, college_id=None, batch_name="学校统排", status="PUBLISHED")
        eb = AaExamBatch(tenant_id=tid, term_id=term.id, batch_name="全校考试", status="PUBLISHED")
        db.add_all([registration, tb, sb, eb]); db.flush()
        ta = AaTeachingTask(tenant_id=tid, batch_id=tb.id, course_id=ca.id, status="READY", teacher_key="teacher-a")
        tb_task = AaTeachingTask(tenant_id=tid, batch_id=tb.id, course_id=cb.id, status="READY", teacher_key="teacher-b")
        db.add_all([ta, tb_task]); db.flush()
        ga = AaGradeTask(tenant_id=tid, teaching_task_id=ta.id, term_id=term.id, term_code="2041-2042-1", status="INPUTTING")
        gb = AaGradeTask(tenant_id=tid, teaching_task_id=tb_task.id, term_id=term.id, term_code="2041-2042-1", status="INPUTTING")
        db.add_all([ga, gb,
            AaRegistration(tenant_id=tid, batch_id=registration.id, student_id=a.id, status="REGISTERED"),
            AaRegistration(tenant_id=tid, batch_id=registration.id, student_id=b.id, status="PENDING_REGISTER"),
            AaRegistrationException(tenant_id=tid, batch_id=registration.id, student_id=b.id, status="OPEN"),
            AaScheduleItem(tenant_id=tid, batch_id=sb.id, task_id=ta.id, weekday=1, slot_no=1, start_week=1, end_week=18, status="EFFECTIVE"),
            AaScheduleItem(tenant_id=tid, batch_id=sb.id, task_id=tb_task.id, weekday=2, slot_no=1, start_week=1, end_week=18, status="EFFECTIVE"),
            AaScheduleChange(tenant_id=tid, term_id=term.id, task_id=tb_task.id, change_type="ADJUST", status="SUBMITTED"),
            AaExamCourse(tenant_id=tid, batch_id=eb.id, teaching_task_id=ta.id, course_id=ca.id, college_id=34, status="CONFIRMED"),
            AaExamCourse(tenant_id=tid, batch_id=eb.id, teaching_task_id=tb_task.id, course_id=cb.id, college_id=12, status="PENDING_CONFIRM")])
        db.flush()
        reg = policy.evaluate_college_registration(db, term.id, {12})
        assert reg["recordCount"] == 1 and reg["result"] == "UNKNOWN"
        assert reg["evidence"][0]["localBlockingCount"] == 0
        grade = semantic.evaluate_grade(db, "2041-2042-1", {}, college_ids={12})
        assert grade["evidence"][0]["unpublishedTaskIds"] == [str(ga.id)]
        operational_schedule = operational.evaluate_schedule(db, term.id, {12})
        assert operational_schedule["present"]
        schedule_result = semantic.evaluate_schedule(db, term.id, operational_schedule, college_ids={12})
        assert schedule_result["result"] == "PASS"
        assert schedule_result["evidence"][0]["readyTasks"] == 1
        assert schedule_result["evidence"][0]["effectiveItems"] == 1
        exam_result = operational.evaluate_exam(db, term.id, {12})
        assert exam_result["recordCount"] == 1 and exam_result["result"] == "UNKNOWN"
        assert exam_result["evidence"][0]["localBlockingCount"] == 0
        db.rollback()
