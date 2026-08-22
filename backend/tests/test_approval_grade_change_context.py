"""PR190 P1：AA_GRADE_CHANGE Context 必须兼容仓库内两条真实生产来源合同。

两条流程的 WorkflowInstance.source_biz_id 都是 AaGradeRecord.id：
- 新正式命令额外用 AaGradeChangeRequest.workflow_instance_id 回链冻结的 before/proposed；
- 历史记录级流程没有 request，prev_* 是 before、当前分项是 proposed。

本测试故意让 changeRequest.id 与 gradeRecord.id 没有任何语义关系，防止 adapter 再次把
sourceBizId 错当 requestId。sourceVersion 必须对齐成绩域正式版本 AaGradeRecord.version_no。
"""
from __future__ import annotations

TID = 1000000000000000001


def _tenant():
    from app.core.context import set_tenant
    set_tenant({"tenantId": str(TID)})


def _seed_grade(db, *, student_id: int, reason: str):
    from app.models import AaGradeRecord, AaGradeTask, WorkflowInstance

    task = AaGradeTask(
        tenant_id=TID, course_name="生产级软件工程", term_code="2026-1",
        status="PUBLISHED", usual_ratio=30, midterm_ratio=0, final_ratio=70, pass_line=60,
    )
    db.add(task); db.flush()
    record = AaGradeRecord(
        tenant_id=TID, task_id=task.id, student_id=student_id,
        usual_score=88, final_score=92, total_score=91, pass_status="PASSED",
        prev_usual_score=80, prev_final_score=85, prev_total_score=84,
        change_reason=reason, version_no=7,
    )
    db.add(record); db.flush()
    inst = WorkflowInstance(
        tenant_id=TID, workflow_code="ACAD_GRADE_CHANGE",
        source_module="academic-affairs", source_biz_type="AA_GRADE_CHANGE",
        source_biz_id=record.id, applicant_id=1, title="成绩更正",
        status="RUNNING", current_node="COLLEGE_REVIEW",
    )
    db.add(inst); db.flush()
    return task, record, inst


def _values(ctx):
    return {f["label"]: f["value"] for section in ctx["sections"] for f in section["fields"]}


def test_legacy_grade_change_uses_grade_record_source(db_mode):
    from app.db.session import get_sessionmaker
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _tenant()
        _task, record, inst = _seed_grade(db, student_id=880001, reason="历史流程更正原因")
        ctx = svc.resolve_context(db, inst, for_update=True)
        assert ctx["completeness"] == svc.FULL, ctx
        assert ctx["sourceBizId"] == str(record.id)
        assert ctx["sourceVersion"] == 7
        values = _values(ctx)
        assert values["更正理由"] == "历史流程更正原因"
        assert values["更正前总评"] == "84"
        assert values["拟改总评"] == "91"
        assert "兼容记录级流程" in ctx["summary"]
    finally:
        db.rollback(); db.close()


def test_new_grade_change_request_is_resolved_by_workflow_instance_not_source_id(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _tenant()
        task, record, inst = _seed_grade(db, student_id=880002, reason="记录上的兼容原因")
        request = AaGradeChangeRequest(
            tenant_id=TID, grade_task_id=task.id, grade_record_id=record.id,
            student_id=record.student_id, source="CHANGE_REQUEST",
            proposed_usual_score=95, proposed_midterm_score=None,
            proposed_final_score=96, proposed_total_score=96,
            proposed_pass_status="PASSED",
            before_usual_score=88, before_midterm_score=None,
            before_final_score=92, before_total_score=91,
            expected_grade_version=record.version_no,
            reason="正式命令冻结的更正原因", workflow_instance_id=inst.id,
            status="PENDING",
        )
        db.add(request); db.flush()
        # 这条断言不是依赖条件，只用于明确测试构造：request 自己有独立主键，
        # Context 不能通过 sourceBizId=request.id 去找它。
        assert request.workflow_instance_id == inst.id

        ctx = svc.resolve_context(db, inst, for_update=True)
        assert ctx["completeness"] == svc.FULL, ctx
        assert ctx["sourceBizId"] == str(record.id)
        assert ctx["sourceVersion"] == 7
        values = _values(ctx)
        assert values["更正理由"] == "正式命令冻结的更正原因"
        assert values["更正前总评"] == "91"
        assert values["拟改总评"] == "96"
        assert "正式更正命令" in ctx["summary"]
    finally:
        db.rollback(); db.close()
