"""Structured before/after evidence for high-risk grade commands.

AA-014/AA-015 production acceptance requires high-risk grade audit rows to carry
machine-readable before/after facts.  The canonical grade write chain already has strict
state preconditions; this guard records those transitions without taking ownership of any
business state, permission, workflow, or grade projection.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from . import academic_affairs_grade_core_service as _core

_ORIGINAL_AUDIT = None
_TASK_ACTIONS = {
    "SUBMIT",
    "COLLEGE_RETURN",
    "COLLEGE_APPROVE",
    "ACADEMIC_RETURN",
    "PUBLISH",
    "ARCHIVE",
}
_RECORD_ACTIONS = {"CHANGE_APPLY", "CHANGE_STEP", "CHANGE_REJECT", "CHANGE_APPROVE"}


def _json(value: dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _task_evidence(db, biz_id: int, action: str, detail: str):
    from app.models import AaGradeTask

    task = db.get(AaGradeTask, int(biz_id))
    if not task or task.tenant_id != _core._tid():
        return None, None

    action = action.upper()
    if action == "SUBMIT":
        # submit accepts exactly INPUTTING or RETURNED.  return_reason is retained after a
        # returned task is resubmitted, so it distinguishes the two legal source states.
        before_status = "RETURNED" if str(task.return_reason or "").strip() else "INPUTTING"
        return (
            {"status": before_status},
            {
                "status": "SUBMITTED",
                "workflowInstanceId": str(task.workflow_instance_id or ""),
            },
        )
    if action == "COLLEGE_RETURN":
        return (
            {"status": "SUBMITTED", "workflowNode": "COLLEGE_REVIEW"},
            {"status": "RETURNED", "returnReason": str(task.return_reason or detail or "")},
        )
    if action == "COLLEGE_APPROVE":
        return (
            {"status": "SUBMITTED", "workflowNode": "COLLEGE_REVIEW"},
            {
                "status": "ACADEMIC_REVIEW",
                "workflowNode": "ACADEMIC_REVIEW",
                "collegeReviewerId": str(task.college_reviewer_id or ""),
            },
        )
    if action == "ACADEMIC_RETURN":
        return (
            {"status": "ACADEMIC_REVIEW", "workflowNode": "ACADEMIC_REVIEW"},
            {"status": "RETURNED", "returnReason": str(task.return_reason or detail or "")},
        )
    if action == "PUBLISH":
        return (
            {"status": "ACADEMIC_REVIEW", "workflowNode": "ACADEMIC_REVIEW"},
            {
                "status": "PUBLISHED",
                "publishAt": task.publish_at,
                "academicReviewerId": str(task.academic_reviewer_id or ""),
                "projection": detail or "",
            },
        )
    if action == "ARCHIVE":
        return ({"status": "PUBLISHED"}, {"status": "ARCHIVED"})
    return None, None


def _latest_change_request(db, record_id: int):
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest

    return db.scalars(
        select(AaGradeChangeRequest)
        .where(
            AaGradeChangeRequest.tenant_id == _core._tid(),
            AaGradeChangeRequest.grade_record_id == int(record_id),
            AaGradeChangeRequest.is_deleted.is_(False),
        )
        .order_by(AaGradeChangeRequest.id.desc())
        .limit(1)
    ).first()


def _record_evidence(db, biz_id: int, action: str, detail: str):
    from app.models import AaGradeRecord

    record = db.get(AaGradeRecord, int(biz_id))
    if not record or record.tenant_id != _core._tid():
        return None, None
    request = _latest_change_request(db, int(biz_id))
    action = action.upper()

    if action == "CHANGE_APPLY" and request:
        # Applying a correction must not mutate the current official fact.  Record the
        # current fact on the left and the proposed command/workflow state on the right.
        return (
            {
                "status": "PUBLISHED",
                "finalScore": request.before_final_score,
                "totalScore": request.before_total_score,
                "currentGradeId": str(request.current_grade_id or ""),
                "gradeVersion": int(request.expected_grade_version or 1),
            },
            {
                "status": "CHANGE_REVIEW",
                "requestStatus": str(request.status or "PENDING"),
                "workflowNode": "COLLEGE_REVIEW",
                "changeRequestId": str(request.id),
                "proposedFinalScore": request.proposed_final_score,
                "proposedTotalScore": request.proposed_total_score,
            },
        )

    if action == "CHANGE_STEP" and request:
        return (
            {
                "status": "CHANGE_REVIEW",
                "requestStatus": "PENDING",
                "workflowNode": "COLLEGE_REVIEW",
                "changeRequestId": str(request.id),
            },
            {
                "status": "CHANGE_REVIEW",
                "requestStatus": "PENDING",
                "workflowNode": "ACADEMIC_REVIEW",
                "changeRequestId": str(request.id),
            },
        )

    if action == "CHANGE_REJECT" and request:
        return (
            {
                "status": "CHANGE_REVIEW",
                "requestStatus": "PENDING",
                "changeRequestId": str(request.id),
                "currentTotalScore": request.before_total_score,
            },
            {
                "status": "PUBLISHED",
                "requestStatus": "REJECTED",
                "changeRequestId": str(request.id),
                "currentTotalScore": request.before_total_score,
                "reason": detail or "",
            },
        )

    if action == "CHANGE_APPROVE" and request:
        return (
            {
                "status": "PUBLISHED",
                "requestStatus": "PENDING",
                "finalScore": request.before_final_score,
                "totalScore": request.before_total_score,
                "gradeId": str(request.current_grade_id or ""),
                "gradeSource": "PUBLISH",
                "gradeRecordStatus": "ACTIVE",
            },
            {
                "status": "PUBLISHED",
                "requestStatus": "APPROVED",
                "finalScore": record.final_score,
                "totalScore": record.total_score,
                "gradeId": str(record.acad_grade_id or ""),
                "gradeSource": "CHANGE",
                "gradeRecordStatus": "ACTIVE",
                "previousGradeStatus": "SUPERSEDED",
                "changeRequestId": str(request.id),
            },
        )
    return None, None


def _structured_evidence(db, biz_type, biz_id, action, detail):
    action_code = str(action or "").upper()
    if not biz_id:
        return None, None
    if biz_type == "AA_GRADE_TASK" and action_code in _TASK_ACTIONS:
        return _task_evidence(db, int(biz_id), action_code, detail or "")
    if biz_type == "AA_GRADE_RECORD" and action_code in _RECORD_ACTIONS:
        return _record_evidence(db, int(biz_id), action_code, detail or "")
    return None, None


def _audit_with_evidence(db, biz_type, biz_id, action, detail=""):
    before, after = _structured_evidence(db, biz_type, biz_id, action, detail)
    if before is None and after is None:
        return _ORIGINAL_AUDIT(db, biz_type, biz_id, action, detail)

    from app.models import AffairsAuditTrail

    name, role, uid = _core._op()
    db.add(
        AffairsAuditTrail(
            tenant_id=_core._tid(),
            biz_type=biz_type,
            biz_id=int(biz_id) if biz_id else None,
            action=action,
            operator=name or uid,
            role_name=role,
            detail=detail,
            before_val=_json(before),
            after_val=_json(after),
            occurred_at=datetime.utcnow(),
        )
    )


_audit_with_evidence._grade_audit_evidence_guard = True


def install() -> None:
    """Idempotently wrap the canonical audit sink; business commands remain unchanged."""
    global _ORIGINAL_AUDIT
    if getattr(_core._audit, "_grade_audit_evidence_guard", False):
        return
    _ORIGINAL_AUDIT = _core._audit
    _core._audit = _audit_with_evidence
