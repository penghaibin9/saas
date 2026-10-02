"""只读流程的状态和学院并行聚合；单元检查不启动真实数据库夹具。"""
from types import SimpleNamespace as Row
from unittest.mock import MagicMock

import pytest

from app.modules.academic_affairs.services import academic_affairs_flow_service as service


@pytest.fixture
def flow_tenant_context(db_mode):
    """真实查询及授权共用请求租户，并在测试结束后恢复，避免局部替身掩盖缺上下文。"""
    from app.core.context import get_tenant, set_tenant
    previous = get_tenant()
    tid = 1000000000000000001
    set_tenant(tid)
    try:
        yield tid
    finally:
        set_tenant(previous)


def unit(cid, state):
    return {"collegeId": str(cid), "stages": [{"stageCode": code, "status": state} for code, *_ in service.STAGES]}


def test_flow_has_twelve_stages_and_exactly_six_states():
    assert len(service.STAGES) == 12
    assert service.STAGES[3][0] == "F40_TEACHING_TASK"
    assert service.FLOW_STATUSES == {"NOT_STARTED", "ACTION_REQUIRED", "BLOCKED", "READY", "DONE", "NOT_APPLICABLE"}


@pytest.mark.parametrize("status,class_name", [("ASSIGNED", "甲教学班"), ("ASSIGNED", None), ("READY", "甲教学班"), ("READY", None)])
def test_teacher_workbench_reads_real_task_class_field(monkeypatch, status, class_name):
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_work_service as work
    from app.modules.academic_affairs.services import academic_affairs_teacher_relation_authority as authority
    task = AaTeachingTask(id=10, tenant_id=1, batch_id=2, course_id=3,
        course_name="公共课", teaching_class_name=class_name, status=status)
    assert not hasattr(task, "class_name")
    monkeypatch.setattr(work, "_tid", lambda: 1)
    monkeypatch.setattr(work, "_user_keys", lambda user: set())
    monkeypatch.setattr(authority, "relation_scope", lambda *args, **kwargs: {"taskIds": {10}})
    db = MagicMock()
    db.scalars.return_value.all.side_effect = [
        [AaTeachingTaskBatch(id=2, tenant_id=1, term_id=4, status="DRAFT")],
        [task], [task], [], [],
    ]
    result = work.current_term_workbench(db, {}, term_id=4)
    assert len(result["actionItems"]) == 1
    item = result["actionItems"][0]
    assert item["id"] == "10"
    if status == "ASSIGNED":
        assert item["kind"] == "TEACHING_TASK"
        assert item["note"] == " · ".join(value for value in (class_name, "学院已分配") if value)
        assert item["path"].endswith("teacher-confirm?taskId=10")
    else:
        assert item["kind"] == "GRADE_SETUP"
        assert item["note"] == f"{class_name or '正式教学班'} · 尚未建立成绩任务"
        assert item["path"].endswith("teachingTaskId=10&action=create")


@pytest.mark.parametrize("courses,batches,expected", [
    ({}, {}, ("NOT_STARTED", "SCHOOL", "exam.manage")),
    ({"PENDING_CONFIRM": 1}, {"DRAFT": 1}, ("ACTION_REQUIRED", "COLLEGE", "exam.manage")),
    ({"CONFIRMED": 1}, {"DRAFT": 1}, ("ACTION_REQUIRED", "SCHOOL", "exam.manage")),
    ({"CONFIRMED": 1}, {"COURSE_CONFIRMED": 1}, ("ACTION_REQUIRED", "SCHOOL", "exam.arrange")),
    ({"CONFIRMED": 1}, {"ARRANGED": 1}, ("ACTION_REQUIRED", "SCHOOL", "exam.publish")),
    ({"CONFIRMED": 1}, {"PUBLISHED": 1}, ("READY", "SCHOOL", "exam.manage")),
    ({"CONFIRMED": 2}, {"FINISHED": 1, "ARCHIVED": 1}, ("DONE", "SCHOOL", "exam.manage")),
    ({"CONFIRMED": 2}, {"PUBLISHED": 1, "COURSE_CONFIRMED": 1}, ("ACTION_REQUIRED", "SCHOOL", "exam.arrange")),
    ({"CONFIRMED": 1}, {"UNRECOGNIZED": 1}, ("BLOCKED", "SCHOOL", "exam.manage")),
])
def test_exam_progress_hands_college_confirmation_to_real_school_batch_stage(courses, batches, expected):
    assert service._exam_progress(courses, batches) == expected


@pytest.mark.parametrize("batch_status,permission", [("COURSE_CONFIRMED", "exam.arrange"), ("ARRANGED", "exam.publish")])
def test_school_exam_projection_uses_current_action_holder(monkeypatch, batch_status, permission):
    monkeypatch.setattr(service.readiness, "_term_setup_items", lambda *args: [])
    rows = [dict(row, label=service.STAGES[index][1]) for index, row in enumerate(unit(12, "DONE")["stages"])]
    rows[7].update(status="ACTION_REQUIRED", evidence={"byStatus": {"CONFIRMED": 1}, "byBatchStatus": {batch_status: 1}})
    calls = []
    def resolve(action):
        calls.append(action)
        return {"resolved": True, "assigneeUserIds": ["17"], "action": action}
    stages = service._school_stages(MagicMock(), Row(id=1), Row(permission_codes=set()),
        [{"collegeName": "甲学院", "stages": rows}], resolve, complete_scope=False)
    assert stages[7]["status"] == "ACTION_REQUIRED"
    assert stages[7]["responsibility"]["action"] == permission
    assert calls.count(permission) == 1
    assert ("exam.publish" if permission == "exam.arrange" else "exam.arrange") not in calls


def test_term_calendar_uses_real_model_datetime_values_and_last_applicable_stage():
    from datetime import date, datetime
    from app.models import AaTerm
    term = AaTerm(start_date=datetime(2041, 9, 1, 0, 0), end_date=datetime(2042, 1, 20, 0, 0))
    assert service._term_date(term.start_date).isoformat() == "2041-09-01"
    assert service._term_date(term.end_date) < date(2042, 1, 21)
    done = {"stageCode": "F30_PROGRAM_COURSE", "status": "DONE"}
    assert service._current([done, {"stageCode": "F120_ARCHIVE", "status": "NOT_APPLICABLE"}]) is done
    assert service._current([{"status": "NOT_APPLICABLE"}]) is None


def test_flow_college_progress_isolated():
    a, b = unit(12, "READY"), unit(34, "BLOCKED")
    gate = service._gate("F40_TEACHING_TASK", "教学任务", [a, b], complete_scope=True)
    assert not gate["ready"]
    assert gate["readyUnitCount"] == 1 and gate["blockedUnitCount"] == 1
    assert a["stages"][3]["status"] == "READY"


def test_college_archive_hands_ready_work_to_school_without_school_write_permission():
    term = Row(id=54, status="PUBLISHED")
    ctx = Row(permission_codes={"academicAffairs.archive.view"})
    rows = [dict(row, label=service.STAGES[index][1])
            for index, row in enumerate(unit(12, "READY")["stages"])]
    local_permissions, school_permissions = [], []

    def org(permission):
        local_permissions.append(permission)
        return {"resolved": True, "permission": permission}

    def school(permission):
        school_permissions.append(permission)
        return {"resolved": False, "permission": permission}

    ready = service._college_archive_stage(rows, term, ctx, 12, org, school)
    assert ready["status"] == "READY" and ready["blockers"] == []
    assert ready["responsibility"]["permission"] == "academicAffairs.archive.view"
    assert ready["evidence"]["schoolResponsibility"]["permission"] == "archive.manage"
    assert "待校教务核验" in ready["evidence"]["scopeNote"]
    assert local_permissions == ["academicAffairs.archive.view"]
    assert school_permissions == ["archive.manage"]

    rows[1]["status"] = "ACTION_REQUIRED"
    blocked = service._college_archive_stage(rows, term, ctx, 12, org, school)
    assert blocked["status"] == "BLOCKED"
    assert blocked["blockers"][0]["code"] == "COLLEGE_NOT_READY"
    assert "schoolResponsibility" not in blocked["evidence"]


def test_unowned_opening_anomalies_belong_to_school_gate_only(monkeypatch):
    from datetime import date
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator
    monkeypatch.setattr(evaluator, "_tid", lambda: 1)
    monkeypatch.setattr(evaluator, "resolve_program_for_scope", lambda *args, **kw: Row(
        status="UNRESOLVED", program=None, rule="NO_BINDING", message="班级尚未绑定方案"))
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [Row(id=1, major_id=999, grade="2041")]
    term = Row(year_code="2041-2042", term_no=1, end_date=date(2042, 1, 20))
    assert evaluator._expected_opening(db, term, college_ids={12}) == ([], [])
    assert evaluator._expected_opening(db, term)[1][0]["type"] == "PROGRAM_UNRESOLVED"
    db.query.return_value.filter.return_value.all.return_value = [Row(id=1, major_id=999, grade="invalid")]
    assert evaluator._expected_opening(db, term, college_ids={12}) == ([], [])
    assert evaluator._expected_opening(db, term)[1][0]["type"] == "TERM_UNRESOLVED"


def test_flow_school_aggregates_all_colleges():
    gate = service._gate("F40_TEACHING_TASK", "教学任务", [unit(12, "READY"), unit(34, "READY")], complete_scope=True)
    assert gate["ready"] and gate["totalUnitCount"] == 2


def test_school_gate_waits_for_required_units_and_full_scope():
    for rows, complete in (([], True), ([unit(12, "READY")], False), ([unit(12, "NOT_STARTED")], True)):
        assert not service._gate("F50_SCHEDULE", "课表发布", rows, complete_scope=complete)["ready"]


def test_school_archive_waits_for_prerequisites_without_hiding_existing_batch(monkeypatch):
    from app.models import AaTerm
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service.readiness, "_term_setup_items", lambda *args: [])
    monkeypatch.setattr(service, "_schedule_projection", lambda *args: ("NOT_APPLICABLE", [], {}, None))
    monkeypatch.setattr(service, "_schedule_change_projection", lambda *args, **kw: None)
    for name in ("evaluate_selection", "evaluate_graduation", "evaluate_evaluation"):
        monkeypatch.setattr(policy, name, lambda *args: {"result": "PASS"})
    evaluate = MagicMock(return_value={"TEACHING_TASK": {"result": "PASS"}})
    monkeypatch.setattr(archive, "_evaluate_domains", evaluate)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = Row(id=21, status="DRAFT", batch_name="学期归档")
    stages = [dict(row, label=service.STAGES[index][1]) for index, row in enumerate(unit(12, "READY")["stages"])]
    stages[1]["status"] = "ACTION_REQUIRED"
    units = [{"collegeName": "甲学院", "stages": stages}]
    term = AaTerm(id=1, year_code="2041-2042", term_no=1, status="ACTIVE")
    ctx, school = Row(permission_codes=set()), lambda _: {"resolved": True}
    result = service._school_stages(db, term, ctx, units, school, complete_scope=True)
    evaluate.assert_not_called()
    assert result[11]["status"] == "BLOCKED"
    assert result[11]["evidence"]["checkedDomainCount"] == 0
    assert result[11]["evidence"]["archiveBatchStatus"] == "DRAFT"
    assert result[11]["currentObject"]["id"] == "21"
    assert "注册学籍" in result[11]["blockers"][0]["message"]
    # 已正式归档仍核验封存事实，不能因现时前置投影不同而跳过已有结果。
    term.status = "ARCHIVED"
    db.query.return_value.filter.return_value.first.return_value.status = "ARCHIVED"
    archived = service._school_stages(db, term, ctx, units, school, complete_scope=True)[11]
    evaluate.assert_called_once()
    assert archived["status"] == "DONE" and archived["evidence"]["checkedDomainCount"] == 1


def test_school_gate_defers_final_reconciliation_but_retains_governance_blockers(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator
    monkeypatch.setattr(service, "_tid", lambda: 1)
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.outerjoin.return_value = query
    query.count.return_value = 1
    monkeypatch.setattr(service, "_query", lambda *args: query)
    expected = MagicMock(return_value=([], [{"type": "PROGRAM_UNRESOLVED"}]))
    final = MagicMock(return_value={"result": "BLOCKED", "summary": "全校课程存在重复任务", "evidence": []})
    monkeypatch.setattr(evaluator, "_expected_opening", expected)
    monkeypatch.setattr(evaluator, "evaluate_teaching_task", final)
    blockers = service._global_gate_blockers(MagicMock(), Row(id=1), {}, run_final_reconciliation=False)
    final.assert_not_called()
    assert {row["code"] for row in blockers} >= {
        "SCHOOL_OPENING_SCOPE_UNRESOLVED", "RESPONSIBILITY_UNRESOLVED", "OFFERING_UNIT_UNRESOLVED"}
    blockers = service._global_gate_blockers(MagicMock(), Row(id=1), {})
    final.assert_called_once()
    expected.assert_called_once()
    assert "SCHOOL_TASK_RECONCILIATION_NOT_READY" in {row["code"] for row in blockers}


def test_unknown_and_empty_evidence_are_never_ready():
    assert service._counts_state({}, done=("PUBLISHED",)) == "NOT_STARTED"
    assert service._counts_state({"FUTURE_ENUM": 1}, done=("PUBLISHED",)) == "BLOCKED"
    assert service._semantic({"result": "UNKNOWN"})[0] == "BLOCKED"
    assert service._semantic({"result": "NOT_APPLICABLE"})[0] == "NOT_APPLICABLE"


def test_grade_projection_uses_live_command_states():
    from app.modules.academic_affairs.services.academic_affairs_grade_service import _EDITABLE
    for state in _EDITABLE:
        assert service._grade_status({state: 1}) == "ACTION_REQUIRED"
        assert service._grade_status({state: 1}, teacher=True) == "ACTION_REQUIRED"
    assert service._grade_status({"SUBMITTED": 1}, teacher=True) == "READY"
    assert service._grade_status({"ACADEMIC_REVIEW": 1}) == "ACTION_REQUIRED"


@pytest.mark.parametrize("counts", [{}, {"SELECTED": 2}, {"PENDING_LOTTERY": 1}, {"LOCKED": 2}])
def test_college_selection_progress_never_assigns_school_batch_commands_to_college(counts):
    school = MagicMock(return_value={"orgType": "SCHOOL", "assigneeUserIds": ["101"], "resolved": True})
    college = MagicMock(return_value={"orgType": "COLLEGE", "assigneeUserIds": ["202"], "resolved": True})
    actor = service._student_stage_responsibility(5, {"byStatus": counts}, college, school)
    assert actor["orgType"] == "SCHOOL" and actor["assigneeUserIds"] == ["101"]
    school.assert_called_once_with("selection.manage")
    college.assert_not_called()


@pytest.mark.parametrize("index,counts,permission,school_owned", [
    (9, {"COLLEGE_REVIEW": 1}, "academicAffairs.graduation.collegeReview", False),
    (9, {"ACADEMIC_REVIEW": 1}, "graduation.final", True),
    (10, {"SUBMITTED": 1}, "academicAffairs.evaluation.appeal.review", False),
])
def test_student_domain_projection_preserves_actual_college_and_school_handoffs(index, counts, permission, school_owned):
    school, college = MagicMock(), MagicMock()
    service._student_stage_responsibility(index, {"byStatus": counts}, college, school)
    (school if school_owned else college).assert_called_once_with(permission)
    (college if school_owned else school).assert_not_called()


def test_pending_schedule_change_prevents_ready_even_after_all_attendance_submitted(monkeypatch):
    person = Row(id=21, real_name="学院受理人")
    groups = [Row(status="SUBMITTED", current_node="COLLEGE_REVIEW", college_id=12,
        task_count=1, assignee_id=21, change_count=1, change_id=301, course_name="跨院课程")]
    monkeypatch.setattr(service, "_schedule_change_groups", lambda *args, **kw: groups)
    monkeypatch.setattr(service, "_query", lambda *args: Row(all=lambda: [person]))
    scoped = MagicMock(return_value=[person])
    monkeypatch.setattr(service.responsibility, "_scoped_holders", scoped)
    term = Row(id=91)
    projection = service._schedule_change_projection(MagicMock(), term, college_id=12)
    stage = service._stage(6, term, status="READY", evidence={"byStatus": {"SUBMITTED": 12}})
    ctx = Row(permission_codes={"academicAffairs.scheduleChange.view"})
    result = service._with_schedule_changes(stage, projection, ctx)
    assert result["status"] == "ACTION_REQUIRED"
    assert result["evidence"]["pendingScheduleChangeCount"] == 1
    assert result["responsibility"]["assigneeUserIds"] == ["21"]
    assert result["responsibility"]["source"] == "WORKFLOW_TASK"
    assert result["currentObject"]["id"] == "301"
    assert result["primaryAction"]["route"].endswith("termId=91&changeId=301")
    assert scoped.call_args.args[2] == "COLLEGE"
    assert scoped.call_args.args[4] == "academicAffairs.scheduleChange.collegeReview"


@pytest.mark.parametrize("task_count,allowed", [(0, True), (2, True), (1, False)])
def test_schedule_change_missing_duplicate_or_revoked_assignee_blocks(task_count, allowed, monkeypatch):
    person = Row(id=21, real_name="原受理人")
    groups = [Row(status="COLLEGE_REVIEW", current_node="ACADEMIC_REVIEW", college_id=12,
        task_count=task_count, assignee_id=21, change_count=2, change_id=301, course_name="课程")]
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service, "_schedule_change_groups", lambda *args, **kw: groups)
    monkeypatch.setattr(service, "_query", lambda *args: Row(all=lambda: [person]))
    monkeypatch.setattr(service.responsibility, "_scoped_holders", lambda *args, **kw: [person] if allowed else [])
    term = Row(id=91)
    projection = service._schedule_change_projection(MagicMock(), term)
    result = service._with_schedule_changes(service._stage(6, term, status="READY"), projection,
        Row(permission_codes={"academicAffairs.scheduleChange.view"}))
    assert result["status"] == "BLOCKED"
    assert result["evidence"]["unresolvedScheduleChangeCount"] == 2
    assert not result["responsibility"]["resolved"]
    assert result["currentObject"] is None
    assert result["primaryAction"]["route"].endswith("schedule-change?termId=91")


def test_teacher_attendance_responsibility_survives_waiting_schedule_change():
    term, ctx = Row(id=91), Row(permission_codes={"academicAffairs.scheduleChange.view"})
    teacher = {"resolved": True, "assigneeUserIds": ["31"]}
    stage = service._stage(6, term, status="ACTION_REQUIRED", responsible=teacher,
        evidence={"pendingAttendanceCount": 1})
    projection = {"count": 1, "unresolvedCount": 0, "responsibility": {"resolved": True, "assigneeUserIds": ["21"]},
        "route": "/admin/academic-affairs/schedule-change?termId=91&changeId=301", "currentObject": {"id": "301"}}
    result = service._with_schedule_changes(stage, projection, ctx, keep_attendance_responsibility=True)
    assert result["responsibility"] is teacher
    assert result["evidence"]["pendingScheduleChangeCount"] == 1
    assert result["evidence"]["pendingAttendanceCount"] == 1


def test_current_workflow_assignee_reaches_flow_responsibility_queue(monkeypatch):
    from contextlib import nullcontext
    from app.models import AaTerm
    monkeypatch.setattr(service, "session", lambda: nullcontext(MagicMock()))
    ctx = Row(scope_type="COLLEGE", college_ids={12}, user_id="db-21",
        permission_codes={"academicAffairs.scheduleChange.view"})
    monkeypatch.setattr(service, "build_affairs_context", lambda *args: ctx)
    monkeypatch.setattr(service.responsibility, "viewer_assignments", lambda *args: [])
    term = AaTerm(id=91, year_code="2041-2042", term_no=1, status="ACTIVE")
    monkeypatch.setattr(service.readiness, "_load_term", lambda *args: term)
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = [Row(id=12, college_name="开课学院")]
    monkeypatch.setattr(service, "_query", lambda *args: query)
    projection = {"count": 1, "unresolvedCount": 0,
        "responsibility": {"resolved": True, "orgId": "12", "assigneeUserIds": ["21"], "source": "WORKFLOW_TASK"},
        "route": "/admin/academic-affairs/schedule-change?termId=91&changeId=301", "currentObject": {"id": "301"}}
    stages = [service._stage(i, term, status="NOT_APPLICABLE") for i in range(12)]
    stages[6] = service._with_schedule_changes(service._stage(6, term, status="READY"), projection, ctx)
    monkeypatch.setattr(service, "_unit_stages", lambda *args: stages)
    monkeypatch.setattr(service, "_school_stages", lambda *args, **kw: stages)
    result = service.flow({"currentRoleCode": "COLLEGE_ADMIN"})
    assert [row["stageCode"] for row in result["currentResponsibilities"]] == ["F70_TEACHING_OPERATION"]
    assert result["myStage"]["currentObject"]["id"] == "301"


def test_mysql_pending_changes_use_offering_scope_live_workflow_and_current_account(flow_tenant_context):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaScheduleChange, AaTeachingTask, AaTeachingTaskBatch,
        AaTerm, College, User, WorkflowInstance, WorkflowTask)
    from tests.support_academic_review_identity import seed_college_review_scope
    from tests.support_schedule_change_identity import seed_schedule_change_identity
    tid = flow_tenant_context
    with get_sessionmaker()() as db:
        colleges = [College(tenant_id=tid, code="V5-CHANGE-A", college_name="开课学院", status="ACTIVE"),
                    College(tenant_id=tid, code="V5-CHANGE-B", college_name="另一学院", status="ACTIVE")]
        term = AaTerm(tenant_id=tid, year_code="2041-2042", term_no=1, status="PUBLISHED",
            start_date=datetime(2041, 9, 1), end_date=datetime(2042, 1, 20))
        db.add_all([*colleges, term]); db.flush()
        ids = seed_schedule_change_identity(db, college_ids=[colleges[0].id])
        seed_college_review_scope(db, college_ids=[colleges[0].id])
        courses = [AaCourse(tenant_id=tid, course_code=f"V5-CHANGE-{i}", course_name=f"课程{i}",
            owner_college_id=college.id) for i, college in enumerate(colleges)]
        batch = AaTeachingTaskBatch(tenant_id=tid, term_id=term.id, college_id=colleges[1].id, batch_name="历史学生学院批次")
        db.add_all([*courses, batch]); db.flush()
        tasks = [AaTeachingTask(tenant_id=tid, batch_id=batch.id, course_id=course.id,
            teacher_key="teacher-own" if i == 0 else "teacher-other", status="READY") for i, course in enumerate(courses)]
        db.add_all(tasks); db.flush()
        rows = []
        for i, (tenant, task) in enumerate(((tid, tasks[0]), (tid, tasks[1]), (tid + 1, tasks[0]))):
            change = AaScheduleChange(tenant_id=tenant, term_id=term.id, task_id=task.id,
                change_type="STOP", teacher_key=task.teacher_key, course_name=task.teacher_key,
                status="SUBMITTED", current_node="COLLEGE_REVIEW")
            db.add(change); db.flush()
            instance = WorkflowInstance(tenant_id=tenant, workflow_code="ACAD_SCHEDULE_CHANGE",
                source_module="academic-affairs", source_biz_type="AA_SCHEDULE_CHANGE", source_biz_id=change.id,
                applicant_id=101 + i, status="RUNNING", current_node="COLLEGE_REVIEW")
            db.add(instance); db.flush()
            change.workflow_instance_id = instance.id
            db.add(WorkflowTask(tenant_id=tenant, instance_id=instance.id, node_code="COLLEGE_REVIEW",
                assignee_id=ids["college_admin01"], status="PENDING"))
            rows.append(change)
        # 当前角色权限读取使用独立会话，需先提交真实身份图再核验只读投影。
        db.commit()
        projection = service._schedule_change_projection(db, term, college_id=colleges[0].id)
        assert projection["count"] == 1 and projection["unresolvedCount"] == 0
        assert projection["currentObject"]["id"] == str(rows[0].id)
        assert projection["responsibility"]["assigneeUserIds"] == [str(ids["college_admin01"])]
        assert service._schedule_change_projection(db, term)["count"] == 2
        assert service._schedule_change_projection(db, term, teacher_keys={"teacher-other"})["count"] == 1
        duplicate = WorkflowTask(tenant_id=tid, instance_id=rows[0].workflow_instance_id,
            node_code="COLLEGE_REVIEW", assignee_id=ids["college_admin01"], status="PENDING")
        db.add(duplicate); db.flush()
        assert service._schedule_change_projection(db, term, college_id=colleges[0].id)["unresolvedCount"] == 1
        db.delete(duplicate)
        person = db.get(User, ids["college_admin01"])
        person.status = "DISABLED"
        db.flush()
        revoked = service._schedule_change_projection(db, term, college_id=colleges[0].id)
        assert revoked["unresolvedCount"] == 1 and not revoked["responsibility"]["resolved"]
        db.rollback()


def test_school_resolver_caches_by_actual_stage_permission(monkeypatch):
    resolver = MagicMock(side_effect=lambda db, permission_code, cache: {"permission": permission_code})
    monkeypatch.setattr(service.responsibility, "resolve_school", resolver)
    school = service._school_resolver(MagicMock(), {})
    assert school("grade.publish")["permission"] == "academicAffairs.grade.publish"
    assert school("archive.manage")["permission"] == "academicAffairs.archive.manage"
    school("grade.publish")
    assert resolver.call_count == 2


def test_read_only_schedule_projection_never_requests_resource_locks(monkeypatch):
    from app.models import AaScheduleBatch
    from app.modules.academic_affairs.services import academic_affairs_schedule_gate_service as gate
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth
    monkeypatch.setattr(service, "_tid", lambda: 1)
    batch = Row(id=20, college_id=None, status="DRAFT")
    def query(db, model, *conditions):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.outerjoin.return_value = q
        q.all.return_value = [batch] if model is AaScheduleBatch else []
        q.count.return_value = 0
        return q
    monkeypatch.setattr(service, "_query", query)
    monkeypatch.setattr(gate, "evaluate", lambda db, b: {
        "complete": False, "invalidTasks": [], "missingTasks": [], "overScheduledTasks": [],
        "hardConflictItems": [], "orphanItemIds": [], "invalidCoordinateItemIds": [],
        "invalidClassroomItemIds": [], "totalTasks": 0, "scheduledTasks": 0,
        "missingTaskCount": 0, "hardConflicts": 0})
    conflicts, live = MagicMock(return_value={"problems": []}), MagicMock(return_value=[])
    monkeypatch.setattr(truth, "validate_school_wide_conflicts", conflicts)
    monkeypatch.setattr(truth, "_live_batch_ids", live)
    monkeypatch.setattr(truth, "_items", lambda db, ids: [])
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    monkeypatch.setattr(service, "_schedule_task_ids", lambda *args: {1})
    service._schedule_batch_projection(db, Row(id=1), batch, 12, {})
    assert conflicts.call_args.kwargs == {"lock": False}
    assert live.call_args.kwargs == {"lock": False}


def test_task_confirmation_uses_college_confirm_permission_after_teacher_confirmation():
    org = MagicMock(side_effect=lambda permission: {"permission": permission})
    school = MagicMock(side_effect=lambda permission: {"schoolPermission": permission})
    pending = {"canAdvance": False, "batchByStatus": {"DRAFT": 1}}
    assert service._task_stage_responsibility(pending, org, school)["permission"] == "academicAffairs.teachingTask.manage"
    pending["canAdvance"] = True
    assert service._task_stage_responsibility(pending, org, school)["permission"] == "academicAffairs.teachingTask.confirm"
    pending["batchByStatus"] = {"COLLEGE_CONFIRMED": 1, "APPROVED": 1}
    assert service._task_stage_responsibility(pending, org, school)["schoolPermission"] == "teachingTask.confirm"


def test_school_public_schedule_cannot_be_hidden_by_finished_professional_batch(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_schedule_policy as policy
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(policy, "public_schedule_mode", lambda db: "SCHOOL_CENTRALIZED", raising=False)
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    professional = Row(id=12, college_id=12, status="PUBLISHED")
    public = Row(id=20, college_id=None, status="DRAFT")
    query.all.return_value = [professional, public]
    monkeypatch.setattr(service, "_query", lambda *args: query)
    monkeypatch.setattr(service, "_schedule_task_ids", lambda db, term, batch, cid, cache: {1} if batch.college_id else {2})
    projected = []
    def project(db, term, batch, cid, cache):
        projected.append(batch.id)
        if batch.college_id:
            return "DONE", [], {"totalTasks": 1, "scheduledTasks": 1, "responsibleOrgType": "COLLEGE"}, batch
        return "BLOCKED", [service._problem("SCHEDULE_NOT_READY", "公共课漏排")], {"totalTasks": 1, "missingTaskCount": 1, "responsibleOrgType": "SCHOOL"}, batch
    monkeypatch.setattr(service, "_schedule_batch_projection", project)
    result = service._schedule_projection(MagicMock(), Row(id=1), 12, {})
    assert projected == [12, 20]
    assert result[0] == "BLOCKED" and result[3] is public
    assert result[2]["totalTasks"] == 2 and result[2]["responsibleOrgType"] == "SCHOOL"
    query.all.return_value = [professional]
    result = service._schedule_projection(MagicMock(), Row(id=1), 12, {})
    assert result[0] == "BLOCKED" and result[1][0]["code"] == "SCHEDULE_BATCH_MISSING"
    assert result[2]["missingTaskCount"] == 1


def test_school_schedule_and_gate_independently_require_public_responsibility(monkeypatch):
    monkeypatch.setattr(service, "_schedule_change_projection", lambda *args, **kw: None)
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service.readiness, "_term_setup_items", lambda *args: [])
    issue = service._problem("SCHEDULE_BATCH_MISSING", "公共课尚未统排")
    monkeypatch.setattr(service, "_schedule_projection", lambda *args: ("BLOCKED", [issue], {"totalTasks": 1}, None))
    for name in ("evaluate_selection", "evaluate_graduation", "evaluate_evaluation"):
        monkeypatch.setattr(policy, name, lambda *args: {"result": "PASS"})
    stages = [dict(row, label=service.STAGES[index][1]) for index, row in enumerate(unit(12, "DONE")["stages"])]
    units = [{"collegeName": "甲学院", "stages": stages}]
    rows = service._school_stages(MagicMock(), Row(id=1, status="PUBLISHED"), Row(permission_codes=set()),
        units, lambda _: {"resolved": True}, complete_scope=True)
    assert rows[4]["status"] == "BLOCKED" and rows[4]["blockers"] == [issue]
    gate = service._gate("F50_SCHEDULE", "排课发布", units, complete_scope=True, extra_blockers=rows[4]["blockers"])
    assert not gate["ready"] and gate["readyUnitCount"] == 1


def test_shared_schedule_tasks_intersect_canonical_mode_and_offering_scope(monkeypatch):
    from app.models import AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_schedule_policy as policy
    monkeypatch.setattr(service, "_tid", lambda: 1)
    calls = []
    def scope(db, batch, *, include_centralized_public=False):
        calls.append((batch.college_id, include_centralized_public))
        return AaTeachingTask.id > 0
    monkeypatch.setattr(policy, "task_scope_condition", scope, raising=False)
    db = MagicMock()
    db.scalars.return_value.all.return_value = [1, 2]
    assert service._schedule_task_ids(db, Row(id=1), Row(college_id=None), 12, {}) == {1, 2}
    assert calls == [(None, False), (12, True)]


def test_empty_unused_schedule_is_not_a_false_blocker_but_orphan_items_are():
    assert service._empty_schedule_check({"totalTasks": 0, "scheduledTasks": 0})
    assert not service._empty_schedule_check({"totalTasks": 0, "orphanItemIds": ["1"]})


def test_mysql_school_public_missing_schedule_blocks_even_when_professional_is_published(flow_tenant_context, monkeypatch):
    """由主控独立库串行运行；真实候选SQL、门禁、正式范围头及冲突核查均不替换。"""
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaTerm, AaTeachingTaskBatch, AaTeachingTask,
        AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead, College)
    from app.modules.academic_affairs.services import academic_affairs_schedule_policy as policy
    tid = flow_tenant_context
    monkeypatch.setattr(policy, "public_schedule_mode", lambda db: "SCHOOL_CENTRALIZED")
    with get_sessionmaker()() as db:
        college = College(tenant_id=tid, code="V5-MIX", college_name="公共专业混合学院", status="ACTIVE")
        term = AaTerm(tenant_id=tid, year_code="2042-2043", term_no=1, status="PUBLISHED",
            start_date=datetime(2042, 9, 1), end_date=datetime(2043, 1, 20), teaching_weeks=18)
        db.add_all([college, term]); db.flush()
        courses = [AaCourse(tenant_id=tid, course_code="V5-MIX-P", course_name="专业课", category="MAJOR_CORE", owner_college_id=college.id),
                   AaCourse(tenant_id=tid, course_code="V5-MIX-C", course_name="公共课", category="PUBLIC_BASIC", owner_college_id=college.id)]
        task_batch = AaTeachingTaskBatch(tenant_id=tid, term_id=term.id, college_id=college.id,
                                        batch_name="正式任务", status="APPROVED")
        professional = AaScheduleBatch(tenant_id=tid, term_id=term.id, college_id=college.id,
                                       batch_name="学院专业课", status="PUBLISHED")
        school = AaScheduleBatch(tenant_id=tid, term_id=term.id, college_id=None,
                                batch_name="学校公共课", status="DRAFT")
        db.add_all([*courses, task_batch, professional, school]); db.flush()
        tasks = [AaTeachingTask(tenant_id=tid, batch_id=task_batch.id, course_id=course.id,
            course_name=course.course_name, status="READY", weekly_hours=1, start_week=1, end_week=18,
            teacher_key=f"v5-mix-{index}", no_auto_schedule=False) for index, course in enumerate(courses)]
        db.add_all(tasks); db.flush()
        db.add_all([AaScheduleItem(tenant_id=tid, batch_id=professional.id, task_id=tasks[0].id,
            course_id=courses[0].id, teacher_key=tasks[0].teacher_key, weekday=1, slot_no=1,
            start_week=1, end_week=18, status="EFFECTIVE"),
            AaScheduleScopeHead(tenant_id=tid, term_id=term.id, scope_type="COLLEGE", scope_id=college.id,
                                active_batch_id=professional.id)])
        db.flush()
        assert service._schedule_task_ids(db, term, school, college.id, {}) == {tasks[1].id}
        assert service._schedule_task_ids(db, term, professional, college.id, {}) == {tasks[0].id}
        result = service._schedule_projection(db, term, college.id, {})
        assert result[0] == "BLOCKED" and result[2]["totalTasks"] == 2
        assert result[2]["components"][0]["status"] == "DONE"
        assert result[2]["missingTaskCount"] == 1 and result[3].id == school.id
        assert service._schedule_projection(db, term, None, {})[0] == "BLOCKED"
        db.add_all([AaScheduleItem(tenant_id=tid, batch_id=school.id, task_id=tasks[1].id,
            course_id=courses[1].id, teacher_key=tasks[1].teacher_key, weekday=2, slot_no=1,
            start_week=1, end_week=18, status="EFFECTIVE"),
            AaScheduleScopeHead(tenant_id=tid, term_id=term.id, scope_type="SCHOOL", scope_id=0,
                                active_batch_id=school.id)])
        school.status = "PUBLISHED"
        db.flush()
        assert service._schedule_projection(db, term, college.id, {})[0] == "DONE"
        assert service._schedule_projection(db, term, None, {})[0] == "DONE"
        courses[1].owner_college_id = None
        db.flush()
        # 候选学院可回退批次归属，但缺正式开课单位仍然阻断，不能被共享批次分院切片绕过。
        assert service._schedule_projection(db, term, college.id, {})[0] == "BLOCKED"
        db.rollback()


def test_program_academic_review_hands_to_school_review_permission(monkeypatch):
    resolver = MagicMock(return_value={"resolved": True})
    monkeypatch.setattr(service.responsibility, "resolve_school", resolver)
    db = MagicMock()
    service._program_responsibility(db, Row(status="ACADEMIC_REVIEW"))
    resolver.assert_called_once_with(db, permission_code="academicAffairs.program.review", cache=None)
    db.query.assert_not_called()


@pytest.mark.parametrize("result,state", [
    ({"result": "BLOCKED", "recordCount": 1, "blockingCount": 2, "summary": "本专业仍有漏开与教师待确认",
      "evidence": [{"type": "TASK_RECONCILIATION", "expected": 2, "actual": 1, "pendingTeacherCount": 1}]}, "BLOCKED"),
    ({"result": "PASS", "recordCount": 2, "blockingCount": 0, "summary": "本专业应开与教学任务一致",
      "evidence": [{"type": "TASK_RECONCILIATION", "expected": 2, "actual": 2, "pendingTeacherCount": 0}]}, "READY"),
    ({"result": "PASS", "recordCount": 0, "blockingCount": 0, "summary": "未发现应开记录",
      "evidence": [{"type": "TASK_RECONCILIATION", "expected": 0, "actual": 0, "pendingTeacherCount": 0}]}, "NOT_STARTED"),
    ({"result": "BLOCKED", "recordCount": 0, "blockingCount": 1, "summary": "学期证据已失效"}, "BLOCKED"),
])
def test_major_view_projects_real_preparation_without_college_commands(result, state, monkeypatch):
    from app.models import AaTerm
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = None
    monkeypatch.setattr(service, "_query", lambda *args: query)
    monkeypatch.setattr(service, "_counts", lambda *args: {"PUBLISHED": 1})
    monkeypatch.setattr(service, "_program_responsibility", lambda *args, **kw: {"resolved": True})
    evaluate = MagicMock(return_value=result)
    monkeypatch.setattr(evaluator, "evaluate_teaching_task", evaluate)
    term, db = AaTerm(id=91), MagicMock()
    stages = service._major_stages(db, term, Row(permission_codes={"academicAffairs.*"}), {12})
    evaluate.assert_called_once_with(db, 91, major_ids={12})
    assert stages[2]["evidence"]["programCount"] == 1
    assert stages[3]["status"] == state and stages[3]["primaryAction"] is None
    assert stages[3]["evidence"]["readOnly"] is True
    assert stages[3]["evidence"]["majorIds"] == ["12"]
    fact = result.get("evidence", [{}])[0]
    assert stages[3]["evidence"]["expectedCourseCount"] == fact.get("expected")
    assert stages[3]["evidence"]["pendingTeacherCount"] == fact.get("pendingTeacherCount")
    assert stages[3]["evidence"]["blockerCount"] == result["blockingCount"]


def test_plain_class_scope_does_not_become_major_scope(monkeypatch):
    from contextlib import nullcontext
    query = MagicMock()
    query.scalars.return_value.all.return_value = []
    monkeypatch.setattr(service, "session", lambda: nullcontext(query))
    monkeypatch.setattr(service, "build_affairs_context", lambda *args: Row(
        scope_type="CLASS", college_ids=set(), user_id="db-21"))
    with pytest.raises(Exception):
        service.flow({"currentRoleCode": "TEACHER"})


def test_flow_exposes_only_trusted_major_scope_as_strings(monkeypatch):
    from contextlib import nullcontext
    from app.models import AaTerm
    monkeypatch.setattr(service, "session", lambda: nullcontext(MagicMock()))
    monkeypatch.setattr(service, "build_affairs_context", lambda *args: Row(
        scope_type="CLASS", college_ids=set(), user_id="db-21"))
    monkeypatch.setattr(service, "_major_scope", lambda *args: {9007199254740993})
    monkeypatch.setattr(service.responsibility, "viewer_assignments", lambda *args: [])
    monkeypatch.setattr(service.readiness, "_load_term", lambda *args: AaTerm(id=91, status="PUBLISHED"))
    monkeypatch.setattr(service, "_major_stages", lambda *args: [])
    result = service.flow({"currentRoleCode": "MAJOR_CUSTOM"})
    assert result["viewer"]["majorIds"] == ["9007199254740993"]
    assert result["unitProgress"] == [] and result["schoolGates"] == []


def test_teacher_confirmed_tasks_wait_for_unit_review_not_teacher_again():
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator
    assert evaluator._pending_teacher_count([Row(status="TEACHER_CONFIRMED", teacher_key="teacher")]) == 0
    assert evaluator._pending_teacher_count([Row(status="ASSIGNED", teacher_key="teacher")]) == 1
    assert evaluator._pending_teacher_count([Row(status="READY", teacher_key=None)]) == 1


def test_mysql_major_preparation_keeps_other_majors_out_and_accounts_for_formal_merged_sources(flow_tenant_context):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaProgram, AaProgramBinding, AaProgramCourse, AaTeachingClass,
        AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major, SchoolClass)
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator
    tid = flow_tenant_context
    with get_sessionmaker()() as db:
        college = College(tenant_id=tid, code="V5-MAJOR", college_name="共同开课学院", status="ACTIVE")
        term = AaTerm(tenant_id=tid, year_code="2041-2042", term_no=1, status="PUBLISHED",
            start_date=datetime(2041, 9, 1), end_date=datetime(2042, 1, 20))
        db.add_all([college, term]); db.flush()
        majors = [Major(tenant_id=tid, college_id=college.id, major_name=f"专业{i}") for i in range(2)]
        course = AaCourse(tenant_id=tid, course_code="V5-MAJOR-C", course_name="共享课程", owner_college_id=college.id)
        batch = AaTeachingTaskBatch(tenant_id=tid, term_id=term.id, college_id=college.id,
            batch_name="共享开课批次", status="APPROVED")
        db.add_all([*majors, course, batch]); db.flush()
        tasks, classes, sources = [], [], []
        for i, major in enumerate(majors):
            clazz = SchoolClass(tenant_id=tid, major_id=major.id, class_name=f"专业{i}班", grade="2041")
            program = AaProgram(tenant_id=tid, major_id=major.id, grade_year="2041", program_name=f"专业{i}方案", status="PUBLISHED")
            db.add_all([clazz, program]); db.flush()
            source = AaProgramCourse(tenant_id=tid, program_id=program.id, course_id=course.id, open_term_no=1)
            db.add(source); db.flush()
            db.add(AaProgramBinding(tenant_id=tid, program_id=program.id, major_id=major.id, class_id=clazz.id,
                grade_year="2041", bound_at=datetime(2041, 8, 1), status="ACTIVE"))
            task = AaTeachingTask(tenant_id=tid, batch_id=batch.id, course_id=course.id, class_id=clazz.id,
                source_program_course_id=source.id, teacher_key="teacher", status="READY" if i == 0 else "ASSIGNED")
            db.add(task); db.flush()
            db.add(AaTeachingClass(tenant_id=tid, teaching_task_id=task.id, term_id=term.id, course_id=course.id,
                class_code=f"V5-MAJOR-{i}", class_name=f"专业{i}教学班", status="ACTIVE"))
            tasks.append(task); classes.append(clazz); sources.append(source)
        # 外专业的无方案治理异常不得污染当前专业。
        db.add(SchoolClass(tenant_id=tid, major_id=999999, class_name="无方案外专业班", grade="2041"))
        db.flush()
        cache = {}
        own = evaluator.evaluate_teaching_task(db, term.id, major_ids={majors[0].id}, cache=cache)
        other = evaluator.evaluate_teaching_task(db, term.id, major_ids={majors[1].id}, cache=cache)
        assert own["result"] == "PASS" and own["recordCount"] == 1
        assert own["evidence"][0]["expected"] == 1
        assert other["result"] == "BLOCKED" and other["evidence"][0]["pendingTeacherCount"] == 1
        tasks[1].status = "TEACHER_CONFIRMED"; db.flush()
        assert evaluator.evaluate_teaching_task(db, term.id, major_ids={majors[1].id})["evidence"][0]["pendingTeacherCount"] == 0
        # 独立成班以本专业精确课程来源核验，不能要求补造行政班。
        tasks[0].class_id, tasks[0].formation_mode = None, "SELECTABLE"; db.flush()
        assert evaluator.evaluate_teaching_task(db, term.id, major_ids={majors[0].id})["result"] == "PASS"
        # 跨专业合班：本专业原任务由另一专业的同批同课正式任务承接。
        tasks[0].class_id, tasks[0].status, tasks[0].merged_into_id = classes[0].id, "MERGED", tasks[1].id
        tasks[1].status = "READY"
        db.flush()
        merged = evaluator.evaluate_teaching_task(db, term.id, major_ids={majors[0].id})
        assert merged["result"] == "PASS" and merged["recordCount"] == 1
        assert merged["evidence"][0]["expected"] == 1
        college_result = evaluator.evaluate_teaching_task(db, term.id, college_ids={college.id})
        assert college_result["result"] == "PASS" and college_result["evidence"][0]["expected"] == 2
        empty = evaluator.evaluate_teaching_task(db, term.id, major_ids=set())
        assert empty["recordCount"] == 0 and empty["evidence"][0]["expected"] == 0
        db.rollback()


def test_teacher_tasks_do_not_invent_schedule_or_invigilation_work(monkeypatch):
    monkeypatch.setattr(service, "_schedule_change_projection", lambda *args, **kw: None)
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_work_service as work
    monkeypatch.setattr(work, "current_term_workbench", lambda *args, **kw: {"actionItems": []})
    from datetime import date
    from app.modules.academic_affairs.services import academic_affairs_teacher_relation_authority as authority
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_service as today
    from app.modules.academic_affairs.services import academic_affairs_invigilation_workbench_service as exams
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(authority, "relation_scope", lambda *args, **kw: {"taskIds": {10}})
    monkeypatch.setattr(service, "_task_projection", lambda *args, **kw: ("READY", [], {}, None, None))
    monkeypatch.setattr(service, "_counts", lambda *args: {})
    monkeypatch.setattr(today, "teacher_today_projection", lambda user: {
        "termId": "1", "items": [], "todayItems": [], "issues": [], "todayDate": "2041-09-01"})
    monkeypatch.setattr(exams, "project_my_invigilations", lambda *args, **kw: {"items": []})
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    ctx = Row(permission_codes={"academicAffairs.teachingTask.view"})
    term = Row(id=1, year_code="2041-2042", term_no=1, start_date=date(2041, 9, 1))
    rows = service._teacher_stages(db, term, {}, ctx)
    assert rows[4]["status"] == "NOT_STARTED"
    assert rows[6]["status"] == "NOT_STARTED"
    assert rows[7]["status"] == "NOT_APPLICABLE"
    actor = {"resolved": True, "assigneeUserIds": ["21"], "orgId": "21"}
    monkeypatch.setattr(service, "_relation_self_actor", lambda *args, **kw: actor)
    monkeypatch.setattr(today, "teacher_today_projection", lambda user: {
        "termId": "1", "items": [{"teachingTaskId": "10"}], "issues": [], "todayDate": "2041-09-01",
        "todayItems": [{"teachingTaskId": "10", "slotNo": 1, "attendanceExecutable": True}]})
    rows = service._teacher_stages(db, term, {}, ctx)
    assert rows[6]["status"] == "ACTION_REQUIRED"
    assert "21" in rows[6]["responsibility"]["assigneeUserIds"]


@pytest.mark.parametrize("existing_state", ["READY", "DONE", "NOT_STARTED"])
def test_teacher_grade_flow_cannot_be_ready_while_official_workbench_has_missing_task(existing_state, monkeypatch):
    from datetime import datetime
    from app.models import AaTerm
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_work_service as work
    projection = MagicMock(return_value={"actionItems": [{"kind": "GRADE_SETUP", "id": "103",
        "title": "开始共享课程成绩录入", "path": "/admin/academic-affairs/grade-entry?teachingTaskId=103&action=create"}]})
    monkeypatch.setattr(work, "current_term_workbench", projection)
    actor = {"resolved": True, "assigneeUserIds": ["21"], "orgId": "21"}
    monkeypatch.setattr(service, "_relation_self_actor", lambda *args, **kw: actor)
    term = AaTerm(id=91, start_date=datetime(2041, 9, 1), end_date=datetime(2042, 1, 20))
    user, db = {"userId": "21"}, MagicMock()
    stage = service._stage(8, term, status=existing_state, evidence={"byStatus": {"PUBLISHED": 1}})
    result = service._with_missing_teacher_grade_tasks(db, term, user, Row(permission_codes={"academicAffairs.grade.input"}), stage)
    projection.assert_called_once_with(db, user, term_id=91, term_start_date="2041-09-01", term_end_date="2042-01-20")
    assert result["status"] == "BLOCKED" and result["evidence"]["missingGradeTaskCount"] == 1
    assert result["responsibility"]["assigneeUserIds"] == ["21"]
    assert result["currentObject"]["id"] == "103"
    assert result["primaryAction"]["route"].endswith("teachingTaskId=103&action=create")
    assert result["blockers"][-1]["code"] == "GRADE_TASK_NOT_CREATED"


def test_missing_grade_task_does_not_offer_create_after_input_permission_revoked(monkeypatch):
    from app.models import AaTerm
    from app.modules.academic_affairs.services import academic_affairs_teacher_today_work_service as work
    monkeypatch.setattr(work, "current_term_workbench", lambda *args, **kw: {"actionItems": [
        {"kind": "GRADE_SETUP", "id": "103", "path": "/admin/academic-affairs/grade-entry?teachingTaskId=103&action=create"}]})
    monkeypatch.setattr(service, "_relation_self_actor", lambda *args, **kw: {
        "resolved": False, "assigneeUserIds": [], "reason": "当前成绩办理权限已撤销"})
    term = AaTerm(id=91)
    result = service._with_missing_teacher_grade_tasks(MagicMock(), term, {}, Row(permission_codes=set()),
        service._stage(8, term, status="READY"))
    assert result["status"] == "BLOCKED" and result["primaryAction"] is None
    assert not result["responsibility"]["resolved"]


def test_college_published_grades_do_not_hide_missing_ready_course(monkeypatch):
    monkeypatch.setattr(service, "_tid", lambda: 1)
    task = Row(id=103, course_name="另一门本院开课课程")
    query = MagicMock()
    query.count.return_value = 1
    query.order_by.return_value.first.return_value = task
    monkeypatch.setattr(service, "_query", lambda *args: query)
    resolver = MagicMock(return_value={"resolved": True, "assigneeUserIds": ["21"]})
    monkeypatch.setattr(service.responsibility, "resolve_teacher", resolver)
    term, ctx, db = Row(id=91), Row(permission_codes={"academicAffairs.grade.view"}), MagicMock()
    stage = service._stage(8, term, status=service._grade_status({"PUBLISHED": 1}),
        evidence={"byStatus": {"PUBLISHED": 1}})
    result = service._with_missing_college_grade_tasks(db, term, 12, ctx, stage)
    assert result["status"] == "BLOCKED" and result["evidence"]["missingGradeTaskCount"] == 1
    assert result["evidence"]["byStatus"] == {"PUBLISHED": 1}
    assert result["currentObject"]["id"] == "103"
    assert result["responsibility"]["assigneeUserIds"] == ["21"]
    assert result["primaryAction"]["route"] == "/admin/academic-affairs/grade-overview?termId=91&collegeId=12"
    resolver.assert_called_once_with(db, task, permission_code="academicAffairs.grade.input", cache=None)
    query.count.return_value = 0
    assert service._with_missing_college_grade_tasks(db, term, 12, ctx, stage) is stage


def test_mysql_college_grade_missing_tasks_follow_ready_offering_scope(flow_tenant_context, monkeypatch):
    """真实 SQL 验证已有完成成绩不会掩盖缺项；由主控串行执行。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaGradeTask, AaTeachingTask, AaTeachingTaskBatch, AaTerm
    tid = flow_tenant_context
    monkeypatch.setattr(service.responsibility, "resolve_teacher", lambda *args, **kw: {
        "resolved": True, "assigneeUserIds": ["21"]})
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=tid, year_code="2041-2042", term_no=1, status="PUBLISHED")
        db.add(term); db.flush()
        batch = AaTeachingTaskBatch(tenant_id=tid, term_id=term.id, college_id=34, batch_name="历史学生学院批次")
        own = AaCourse(tenant_id=tid, course_code="V5-GRADE-A", course_name="本院开课", owner_college_id=12)
        other = AaCourse(tenant_id=tid, course_code="V5-GRADE-B", course_name="外院开课", owner_college_id=34)
        db.add_all([batch, own, other]); db.flush()
        tasks = [AaTeachingTask(tenant_id=tenant, batch_id=batch.id, course_id=course.id,
            course_name=course.course_name, status=state, is_deleted=deleted)
            for tenant, course, state, deleted in ((tid, own, "READY", False), (tid, own, "READY", False),
                (tid, other, "READY", False), (tid, own, "ASSIGNED", False),
                (tid + 1, own, "READY", False), (tid, own, "READY", True))]
        db.add_all(tasks); db.flush()
        db.add(AaGradeTask(tenant_id=tid, term_id=term.id, teaching_task_id=tasks[0].id, status="PUBLISHED"))
        # 外租户的同任务成绩记录不能掩盖本租户缺项。
        db.add(AaGradeTask(tenant_id=tid + 1, term_id=term.id, teaching_task_id=tasks[1].id, status="PUBLISHED"))
        db.flush()
        ctx = Row(permission_codes={"academicAffairs.grade.view"})
        stage = service._stage(8, term, status="DONE", evidence={"byStatus": {"PUBLISHED": 1}})
        result = service._with_missing_college_grade_tasks(db, term, 12, ctx, stage)
        assert result["status"] == "BLOCKED" and result["evidence"]["missingGradeTaskCount"] == 1
        assert result["currentObject"]["id"] == str(tasks[1].id)
        own.owner_college_id = None
        db.flush()
        assert service._with_missing_college_grade_tasks(db, term, 12, ctx, stage) is stage
        fallback = service._with_missing_college_grade_tasks(db, term, 34, ctx, stage)
        assert fallback["evidence"]["missingGradeTaskCount"] == 2
        own.owner_college_id = 12
        db.add(AaGradeTask(tenant_id=tid, term_id=term.id, teaching_task_id=tasks[1].id, status="NOT_STARTED"))
        db.flush()
        assert service._with_missing_college_grade_tasks(db, term, 12, ctx, stage) is stage
        db.rollback()


def test_unresolved_responsibility_blocks_real_in_progress_node():
    stage = service._stage(3, Row(id=1), status="ACTION_REQUIRED",
        responsible={"resolved": False, "reason": "学院未配置秘书", "blockerCode": "ASSIGNMENT_EXPIRED"})
    assert stage["status"] == "BLOCKED"
    assert stage["blockers"][0]["code"] == "ASSIGNMENT_EXPIRED"
    assert stage["primaryAction"] is None


def test_college_cannot_request_other_college(monkeypatch):
    db = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = db
    monkeypatch.setattr(service, "session", lambda: context)
    monkeypatch.setattr(service, "build_affairs_context", lambda user, db: Row(
        scope_type="COLLEGE", college_ids={12}))
    with pytest.raises(Exception) as raised:
        service.flow({"currentRoleCode": "COLLEGE_ADMIN"}, college_id=34)
    assert "其他学院" in str(raised.value)
    db.query.assert_not_called()


def test_teacher_never_receives_school_matrix_or_gate(monkeypatch):
    db, cm = MagicMock(), MagicMock()
    cm.__enter__.return_value = db
    monkeypatch.setattr(service, "session", lambda: cm)
    monkeypatch.setattr(service, "build_affairs_context", lambda user, db: Row(
        scope_type="NONE", college_ids=set(), user_id="db-21"))
    monkeypatch.setattr(service.readiness, "_load_term", lambda db, tid: None)
    monkeypatch.setattr(service.responsibility, "viewer_assignments", lambda db, uid: [])
    monkeypatch.setattr(service, "_teacher_stages", lambda *args: [])
    result = service.flow({"currentRoleCode": "ACADEMIC_TEACHER"})
    assert result["unitProgress"] == [] and result["schoolGates"] == [] and result["schoolStage"] is None
    assert result["viewer"]["scopeType"] == "ASSIGNED"


def test_mysql_task_batch_progress_keeps_colleges_and_tenants_isolated(flow_tenant_context):
    """仅由主控在独立 MySQL 测试库串行执行；不是多角色浏览器验收。"""
    from datetime import date, datetime
    from app.db.session import get_sessionmaker
    from app.models import (AaTerm, AaTeachingClass, AaTeachingTask, AaTeachingTaskBatch,
        AaCourse, AaProgram, AaProgramCourse, AaProgramBinding, College, Major, SchoolClass)
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator

    tid = flow_tenant_context
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=tid, year_code="2041-2042", term_no=1, term_name="责任范围测试",
                      start_date=date(2041, 9, 1), end_date=date(2042, 1, 20), teaching_weeks=18,
                      exam_week_start=17, status="PUBLISHED")
        db.add(term)
        db.flush()
        # 学生属于学院34，课程由学院12开设；不能按学生学院删掉学院12应承担的需求。
        db.add_all([College(id=12, tenant_id=tid, college_name="开课学院"),
                    College(id=34, tenant_id=tid, college_name="学生学院")])
        major = Major(tenant_id=tid, college_id=34, major_name="跨院测试专业")
        db.add(major)
        db.flush()
        clazz = SchoolClass(tenant_id=tid, major_id=major.id, class_name="跨院学生班", grade="2041")
        course = AaCourse(tenant_id=tid, course_code="V5-CROSS", course_name="跨院课程", owner_college_id=12, status="ENABLED")
        program = AaProgram(tenant_id=tid, major_id=major.id, grade_year="2041", program_name="跨院方案", status="PUBLISHED")
        db.add_all([clazz, course, program])
        db.flush()
        program_course = AaProgramCourse(tenant_id=tid, program_id=program.id, course_id=course.id, open_term_no=1)
        db.add_all([program_course,
                    AaProgramBinding(tenant_id=tid, program_id=program.id, major_id=major.id,
                        class_id=clazz.id, grade_year="2041", bound_at=datetime(2041, 8, 1), status="ACTIVE")])
        for college_id, state, batch_state, tenant in ((12, "READY", "APPROVED", tid),
                (34, "PENDING_ASSIGN", "DRAFT", tid), (12, "PENDING_ASSIGN", "DRAFT", tid + 99)):
            batch = AaTeachingTaskBatch(tenant_id=tenant, term_id=term.id, college_id=college_id,
                                        batch_name=f"学院{college_id}批次", status=batch_state)
            db.add(batch)
            db.flush()
            task = AaTeachingTask(tenant_id=tenant, batch_id=batch.id, course_id=course.id, class_id=clazz.id,
                                  teacher_key="teacher" if state == "READY" else None, status=state)
            db.add(task)
            db.flush()
            if tenant == tid and college_id == 12:
                own_task = task
            db.add(AaTeachingClass(tenant_id=tenant, teaching_task_id=task.id, term_id=term.id,
                course_id=course.id, class_code=f"V5-{tenant}-{college_id}", class_name="责任范围教学班", status="ACTIVE"))
        db.flush()
        a = service._task_projection(db, term, 12)
        b = service._task_projection(db, term, 34)
        assert a[0] == "READY" and a[2]["taskTotal"] == 1
        assert b[0] == "BLOCKED" and b[2]["unassignedCount"] == 1
        assert a[2]["unassignedCount"] == 0
        assert a[2]["openingReconciliation"]["result"] == "PASS"
        # 别院无方案是学校治理阻断，不能倒灌为开课学院12的缺课。
        db.add(SchoolClass(tenant_id=tid, major_id=999, class_name="尚未配置方案", grade="2041"))
        db.flush()
        assert service._task_projection(db, term, 12)[0] == "READY"
        assert any(row.get("type") == "PROGRAM_UNRESOLVED" for row in evaluator.evaluate_teaching_task(db, term.id)["evidence"])
        # 自主选课使用正式教学班和精确方案课程来源，不补造行政班。
        own_task.class_id = None
        own_task.formation_mode = "SELECTABLE"
        own_task.source_program_course_id = program_course.id
        db.flush()
        assert service._task_projection(db, term, 12)[0] == "READY"
        course.owner_college_id = None
        db.flush()
        assert service._task_projection(db, term, 12)[0] == "BLOCKED"
        db.rollback()


def _seed_v5_live_responsibility_identity(db, tid, *, role_code, scope_type, scope_id, org_type, permissions):
    """只在隔离测试库建立正式账号、角色、范围和任职，不替换授权解析。"""
    from datetime import datetime
    from app.models import Role, RoleAssignmentScope, RolePermission, StaffAssignment, User, UserRole
    from tests.support_academic_review_identity import _ensure_permission

    account = User(tenant_id=tid, login_name="v5-live-responsibility", real_name="责任范围测试人员",
        user_type="TEACHER", password_hash="unused-in-service-test", status="ACTIVE")
    role = Role(tenant_id=tid, role_code=role_code, role_name="责任范围测试岗位",
        role_type="SYSTEM" if role_code == "COLLEGE_ADMIN" else "CUSTOM", status="ACTIVE")
    db.add_all([account, role]); db.flush()
    link = UserRole(tenant_id=tid, user_id=account.id, role_id=role.id, status="ACTIVE")
    db.add(link); db.flush()
    grants = {}
    for code in permissions:
        grant = RolePermission(tenant_id=tid, role_id=role.id,
            permission_id=_ensure_permission(db, code).id, status="ACTIVE")
        db.add(grant); grants[code] = grant
    db.add(RoleAssignmentScope(tenant_id=tid, user_role_id=link.id, user_id=account.id,
        role_code=role_code, scope_type=scope_type, scope_id=scope_id, status="ACTIVE",
        effective_at=datetime(2020, 1, 1)))
    appointment = StaffAssignment(tenant_id=tid, user_id=account.id, org_type=org_type,
        org_node_id=scope_id, assignment_type="LEADER", status="ACTIVE", effective_at=datetime(2020, 1, 1))
    db.add(appointment); db.flush()
    claims = {"tenantId": str(tid), "userId": str(account.id), "loginName": account.login_name,
        "userType": "TEACHER", "currentRoleCode": role_code, "activeContextId": f"role:{role.id}"}
    return claims, appointment, grants


def test_mysql_major_leader_resolves_only_live_own_appointment_and_permission(flow_tenant_context):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, College, Major
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as responsibility

    tid = flow_tenant_context
    with get_sessionmaker()() as db:
        college = College(tenant_id=tid, college_name="负责人测试学院", status="ACTIVE")
        db.add(college); db.flush()
        majors = [Major(tenant_id=tid, college_id=college.id, major_name=f"负责人专业{i}", status="ACTIVE") for i in range(2)]
        db.add_all(majors); db.flush()
        programs = [AaProgram(tenant_id=tid, major_id=major.id, program_name=f"负责人方案{i}",
            grade_year="2041", status="DRAFT") for i, major in enumerate(majors)]
        db.add_all(programs)
        # 复用现有方案审核测试岗位，不新增产品角色或改变学校流程政策。
        claims, appointment, grants = _seed_v5_live_responsibility_identity(db, tid,
            role_code="V5_PROGRAM_COLLEGE_REVIEWER", scope_type="MAJOR", scope_id=majors[0].id,
            org_type="MAJOR", permissions=["academicAffairs.program.manage"])
        db.commit()
        own = responsibility.resolve_program(db, programs[0])
        assert own["resolved"] and own["assigneeUserIds"] == [claims["userId"]]
        assert own["orgType"] == "MAJOR" and own["orgId"] == str(majors[0].id)
        assert not responsibility.resolve_program(db, programs[1])["resolved"]
        appointment.org_node_id = majors[1].id; db.commit()
        assert not responsibility.resolve_program(db, programs[0])["resolved"]
        assert not responsibility.resolve_program(db, programs[1])["resolved"], "外专业任职不能绕过本人正式专业范围"
        appointment.org_node_id = majors[0].id
        appointment.expires_at = datetime(2020, 1, 2); db.commit()
        expired = responsibility.resolve_program(db, programs[0])
        assert not expired["resolved"] and expired["blockerCode"] == "ASSIGNMENT_EXPIRED"
        appointment.expires_at = None; db.commit()
        assert responsibility.resolve_program(db, programs[0])["resolved"]
        grants["academicAffairs.program.manage"].status = "DISABLED"; db.commit()
        assert not responsibility.resolve_program(db, programs[0])["resolved"]


def test_mysql_college_leader_assignment_keeps_flow_in_own_college(flow_tenant_context):
    from datetime import datetime
    from app.core.affairs_security import build_affairs_context
    from app.core.exceptions import AppException
    from app.core.permissions import has_permission
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, College
    from app.modules.system_admin.services import role_template_service as templates

    tid = flow_tenant_context
    permissions = ["academicAffairs.term.view", "academicAffairs.program.view"]
    draft = templates.create_draft(template_code="COLLEGE_ADMIN", template_name="学院管理测试模板",
        permission_codes=permissions, change_reason="隔离库学院负责人范围回归", actor_user_id=None)
    templates.publish_draft(int(draft["id"]), expected_version=int(draft["version"]), actor_user_id=None)
    with get_sessionmaker()() as db:
        colleges = [College(tenant_id=tid, college_name=f"负责人范围学院{i}", status="ACTIVE") for i in range(2)]
        term = AaTerm(tenant_id=tid, year_code="2041-2042", term_no=1, status="PUBLISHED",
            start_date=datetime(2041, 9, 1), end_date=datetime(2042, 1, 20))
        db.add_all([*colleges, term]); db.flush()
        claims, appointment, _grants = _seed_v5_live_responsibility_identity(db, tid,
            role_code="COLLEGE_ADMIN", scope_type="COLLEGE", scope_id=colleges[0].id,
            org_type="COLLEGE", permissions=[])
        own_id, other_id, term_id = int(colleges[0].id), int(colleges[1].id), int(term.id)
        db.commit()
        ctx = build_affairs_context(claims, db)
        assert ctx.scope_type == "COLLEGE" and ctx.college_ids == {own_id}
    for requested in (None, own_id):
        result = service.flow(claims, term_id=term_id, college_id=requested)
        assert result["viewer"]["scopeType"] == "COLLEGE"
        assert result["viewer"]["collegeIds"] == [str(own_id)]
        assert any(row["orgType"] == "COLLEGE" and row["orgId"] == str(own_id)
            and row["assignmentType"] == "LEADER" for row in result["viewer"]["assignments"])
        assert [row["collegeId"] for row in result["unitProgress"]] == [str(own_id)]
        assert result["schoolStage"] is None and result["schoolGates"] == []
        assert all(not row["primaryAction"] or row["primaryAction"]["label"].startswith("查看") for row in result["stages"])
    with pytest.raises(AppException) as denied:
        service.flow(claims, term_id=term_id, college_id=other_id)
    assert denied.value.code == "NO_DATA_SCOPE" and denied.value.http_status == 403
    for code in ("academicAffairs.term.manage", "academicAffairs.selection.manage", "academicAffairs.grade.publish", "academicAffairs.archive.manage"):
        assert not has_permission(claims, code)
