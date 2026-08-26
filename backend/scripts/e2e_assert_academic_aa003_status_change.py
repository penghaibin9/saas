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
        req(change.from_status == "REGISTERED", f"AA-003 from_status={change.from_status}")
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
        req(stage_events[0].from_stage == "REGISTERED" and stage_events[0].to_stage == "SUSPENDED",
            f"AA-003 stage event={stage_events[0].from_stage}->{stage_events[0].to_stage}")

        facts = db.scalars(select(StudentAcademicFact).where(
            StudentAcademicFact.tenant_id == tid,
            StudentAcademicFact.student_id == student_id,
            StudentAcademicFact.source_ref_id == change_id,
            StudentAcademicFact.source_type == "SUSPEND",
        ).order_by(StudentAcademicFact.version_no)).all()
        req(len(facts) == 1, f"AA-003 canonical academic fact count={len(facts)}")
        req(facts[0].student_status == "SUSPENDED", f"AA-003 fact status={facts[0].student_status}")

        seal = {
            "tenantId": str(tid),
            "studentId": str(student_id),
            "changeId": str(change_id),
            "changeCount": len(changes),
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
            "academicFactVersion": int(facts[0].version_no),
            "sameCaseResubmit": True,
        }
        SEAL_PATH.write_text(json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(seal, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
