"""Direct MySQL seal for AA-003 status-change Gold Deep."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AaStatusChange,
    AffairsAuditTrail,
    MessageEventOutbox,
    StudentAcademicFact,
    StudentProfile,
    StudentStageEvent,
    UnifiedTodo,
    WorkflowInstance,
    WorkflowTask,
)

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "backend/tmp/e2e_academic_aa003_state.local.json"
OUTCOME_PATH = ROOT / "e2e/academic-aa003-browser-outcome.json"
SEAL_PATH = ROOT / "e2e/academic-aa003-mysql-seal.json"


def req(value, message):
    if not value:
        raise AssertionError(message)


def main() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    outcome = json.loads(OUTCOME_PATH.read_text(encoding="utf-8"))
    tid = int(state["tenantId"])
    student_id = int(state["studentId"])
    change_id = int(outcome["changeId"])
    modified_reason = str(outcome["modifiedReason"])
    base_status = str(state["studentBaseStatus"])
    baseline_fact_id = int(state["academicBaselineFactId"])
    baseline_fact_version = int(state["academicBaselineFactVersion"])

    db = get_sessionmaker()()
    try:
        changes = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == tid,
            AaStatusChange.student_id == student_id,
            AaStatusChange.change_type == "SUSPEND",
            AaStatusChange.is_deleted.is_(False),
        ).order_by(AaStatusChange.id)).all()
        req(len(changes) == 1, f"AA-003 must keep one SUSPEND row after RETURN/resubmit, got {[r.id for r in changes]}")
        change = changes[0]
        req(int(change.id) == change_id, f"AA-003 changeId drifted: db={change.id} browser={change_id}")
        req(change.status == "EFFECTIVE", f"AA-003 final status={change.status}")
        req(change.from_status == base_status, f"AA-003 from_status={change.from_status}, expected={base_status}")
        req(change.to_status == "SUSPENDED", f"AA-003 to_status={change.to_status}")
        req(change.reason == modified_reason, f"AA-003 resubmitted reason not preserved: {change.reason!r}")
        req(change.current_task_id is None, f"AA-003 final current_task_id={change.current_task_id}")
        req(change.workflow_instance_id is not None, "AA-003 workflow_instance_id missing")
        req(str(change.term_code or "") == state["termCode"], f"AA-003 term_code={change.term_code}")

        student = db.get(StudentProfile, student_id)
        req(student is not None, "AA-003 target student missing")
        req(student.student_status == "SUSPENDED", f"AA-003 StudentProfile status={student.student_status}")
        req(int(student.version or 0) == int(state["studentBaseVersion"]) + 1,
            f"AA-003 StudentProfile version advanced incorrectly: base={state['studentBaseVersion']} final={student.version}")

        instances = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == tid,
            WorkflowInstance.source_module == "academic-affairs",
            WorkflowInstance.source_biz_type == "AA_STATUS_CHANGE",
            WorkflowInstance.source_biz_id == change_id,
            WorkflowInstance.is_deleted.is_(False),
        ).order_by(WorkflowInstance.id)).all()
        req(len(instances) == 1, f"AA-003 must reuse one workflow instance, got {[r.id for r in instances]}")
        instance = instances[0]
        req(int(instance.id) == int(change.workflow_instance_id), "AA-003 change/workflow instance link drifted")
        req(instance.status == "APPROVED", f"AA-003 workflow final status={instance.status}")

        tasks = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == tid,
            WorkflowTask.instance_id == int(instance.id),
            WorkflowTask.is_deleted.is_(False),
        ).order_by(WorkflowTask.id)).all()
        task_shape = [(r.node_code, r.status, int(r.assignee_id or 0)) for r in tasks]
        req(len(tasks) == 4, f"AA-003 expected 4 task history rows, got {task_shape}")
        counselor = [r for r in tasks if r.node_code == "COUNSELOR_REVIEW"]
        college = [r for r in tasks if r.node_code == "COLLEGE_REVIEW"]
        office = [r for r in tasks if r.node_code == "AA_OFFICE_FINAL"]
        req(len(counselor) == 2, f"AA-003 counselor task history={task_shape}")
        req(sorted(r.status for r in counselor) == ["APPROVED", "TRANSFERRED"], f"AA-003 counselor statuses={task_shape}")
        req(len(college) == 1 and college[0].status == "APPROVED", f"AA-003 college task={task_shape}")
        req(len(office) == 1 and office[0].status == "APPROVED", f"AA-003 office task={task_shape}")
        req({int(r.assignee_id or 0) for r in counselor} == {int(state["accounts"]["counselor"]["userId"])},
            f"AA-003 counselor assignee drift={task_shape}")
        req(int(college[0].assignee_id or 0) == int(state["accounts"]["college"]["userId"]),
            f"AA-003 college assignee={college[0].assignee_id}")
        req(int(office[0].assignee_id or 0) == int(state["accounts"]["office"]["userId"]),
            f"AA-003 office assignee={office[0].assignee_id}")

        audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid,
            AffairsAuditTrail.biz_type == "AA_STATUS_CHANGE",
            AffairsAuditTrail.biz_id == change_id,
        ).order_by(AffairsAuditTrail.id)).all()
        audit_counts = Counter(str(row.action or "") for row in audits)
        for action, count in {
            "SUBMIT": 1,
            "RETURNED": 1,
            "RESUBMIT": 1,
            "STEP": 2,
            "EFFECTIVE": 1,
        }.items():
            req(audit_counts[action] == count, f"AA-003 audit {action}={audit_counts[action]} all={dict(audit_counts)}")
        req(sum(audit_counts.values()) == 6, f"AA-003 unexpected canonical audit rows={dict(audit_counts)}")
        resubmit_audit = next(row for row in audits if row.action == "RESUBMIT")
        req("sameChangeId=1" in str(resubmit_audit.detail or ""), f"AA-003 RESUBMIT detail={resubmit_audit.detail}")

        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == tid,
            UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_type == "AA_STATUS_CHANGE",
            UnifiedTodo.source_biz_id == change_id,
            UnifiedTodo.todo_type == "AA_STATUS_APPROVAL",
            UnifiedTodo.is_deleted.is_(False),
        ).order_by(UnifiedTodo.id)).all()
        req(todos, "AA-003 approval todo history missing")
        req(all(row.status == "DONE" for row in todos), f"AA-003 final todos not all DONE: {[(r.id,r.assignee_id,r.status) for r in todos]}")

        outbox = db.scalars(select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == tid,
            MessageEventOutbox.source_module == "academic-affairs",
            MessageEventOutbox.source_biz_type == "AA_STATUS_CHANGE",
            MessageEventOutbox.source_biz_id == change_id,
        ).order_by(MessageEventOutbox.id)).all()
        event_codes = [str(row.event_code or "") for row in outbox]
        req("STATUS_CHANGE.RETURNED" in event_codes, f"AA-003 returned message outbox missing: {event_codes}")
        req("STATUS_CHANGE.RESULT" in event_codes, f"AA-003 final message outbox missing: {event_codes}")

        stage_events = db.scalars(select(StudentStageEvent).where(
            StudentStageEvent.tenant_id == tid,
            StudentStageEvent.student_id == student_id,
            StudentStageEvent.source_module == "academic-affairs",
            StudentStageEvent.reason == "学籍异动（SUSPEND）",
        ).order_by(StudentStageEvent.id)).all()
        req(len(stage_events) == 1, f"AA-003 formal stage event count={len(stage_events)}")
        req(stage_events[0].from_stage == base_status and stage_events[0].to_stage == "SUSPENDED",
            f"AA-003 stage event={stage_events[0].from_stage}->{stage_events[0].to_stage}, expected={base_status}->SUSPENDED")

        baseline = db.get(StudentAcademicFact, baseline_fact_id)
        req(baseline is not None, f"AA-003 baseline fact {baseline_fact_id} missing")
        req(int(baseline.student_id) == student_id and int(baseline.tenant_id) == tid,
            f"AA-003 baseline fact ownership drift: tenant={baseline.tenant_id} student={baseline.student_id}")
        req(int(baseline.version_no) == baseline_fact_version,
            f"AA-003 baseline fact version drift: {baseline.version_no} != {baseline_fact_version}")
        req(baseline.student_status == base_status,
            f"AA-003 baseline fact status={baseline.student_status}, expected={base_status}")
        req(baseline.valid_to is not None, "AA-003 final approval must close the previous current fact")

        facts = db.scalars(select(StudentAcademicFact).where(
            StudentAcademicFact.tenant_id == tid,
            StudentAcademicFact.student_id == student_id,
            StudentAcademicFact.source_ref_id == change_id,
            StudentAcademicFact.source_type == "SUSPEND",
        ).order_by(StudentAcademicFact.version_no)).all()
        req(len(facts) == 1, f"AA-003 canonical academic fact count={len(facts)}")
        applied_fact = facts[0]
        req(applied_fact.student_status == "SUSPENDED", f"AA-003 fact status={applied_fact.student_status}")
        req(int(applied_fact.version_no) == baseline_fact_version + 1,
            f"AA-003 academic fact version must advance once: baseline={baseline_fact_version} applied={applied_fact.version_no}")
        req(applied_fact.valid_to is None, "AA-003 applied fact must be the one current fact")
        req(baseline.valid_to == applied_fact.valid_from,
            f"AA-003 fact timeline must be contiguous: old.valid_to={baseline.valid_to} new.valid_from={applied_fact.valid_from}")

        active_facts = db.scalars(select(StudentAcademicFact).where(
            StudentAcademicFact.tenant_id == tid,
            StudentAcademicFact.student_id == student_id,
            StudentAcademicFact.valid_to.is_(None),
        )).all()
        req(len(active_facts) == 1 and int(active_facts[0].id) == int(applied_fact.id),
            f"AA-003 must leave exactly one current fact: {[(r.id, r.version_no, r.student_status) for r in active_facts]}")

        seal = {
            "tenantId": str(tid),
            "studentId": str(student_id),
            "changeId": str(change_id),
            "changeCount": len(changes),
            "baseStudentStatus": base_status,
            "finalStatus": change.status,
            "studentStatus": student.student_status,
            "studentVersion": int(student.version or 0),
            "workflowInstanceId": str(instance.id),
            "workflowInstanceCount": len(instances),
            "tasks": [
                {"id": str(r.id), "node": r.node_code, "status": r.status, "assigneeId": str(r.assignee_id or "")}
                for r in tasks
            ],
            "auditCounts": dict(audit_counts),
            "todoStatuses": [r.status for r in todos],
            "outboxEventCodes": event_codes,
            "baselineAcademicFactId": str(baseline.id),
            "baselineAcademicFactVersion": int(baseline.version_no),
            "academicFactId": str(applied_fact.id),
            "academicFactVersion": int(applied_fact.version_no),
            "sameCaseResubmit": True,
        }
        SEAL_PATH.write_text(json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(seal, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
