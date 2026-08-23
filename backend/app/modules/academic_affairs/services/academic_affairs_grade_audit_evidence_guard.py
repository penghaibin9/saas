"""Production audit evidence guard for high-risk Academic Affairs grade transitions.

The canonical grade service already owns authorization, state transitions and transaction boundaries.
This guard only enriches its existing ``AffairsAuditTrail`` write point with structured before/after
snapshots for high-risk actions. It never changes permissions, workflow routing or business status.

Installed from ``services.__init__`` so HTTP, scripts and internal callers share the same evidence rule.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

_INSTALLED = False


def _json(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _task_snapshots(db, task_id: int, action: str):
    from app.models import AaGradeTask

    task = db.get(AaGradeTask, int(task_id))
    if not task:
        return None, None

    common = {
        "gradeTaskId": int(task.id),
        "teachingTaskId": int(task.teaching_task_id) if task.teaching_task_id else None,
        "termId": int(task.term_id) if task.term_id else None,
        "courseName": task.course_name or "",
    }
    if action == "SUBMIT":
        before_status = "RETURNED" if (task.return_reason or "").strip() else "INPUTTING"
        return (
            {**common, "status": before_status},
            {
                **common,
                "status": "SUBMITTED",
                "workflowInstanceId": int(task.workflow_instance_id) if task.workflow_instance_id else None,
                "submittedAt": task.submitted_at,
            },
        )
    if action == "COLLEGE_RETURN":
        return (
            {**common, "status": "SUBMITTED"},
            {**common, "status": "RETURNED", "returnReason": task.return_reason or ""},
        )
    if action == "COLLEGE_APPROVE":
        return (
            {**common, "status": "SUBMITTED"},
            {
                **common,
                "status": "ACADEMIC_REVIEW",
                "collegeReviewerId": int(task.college_reviewer_id) if task.college_reviewer_id else None,
                "collegeReviewedAt": task.college_reviewed_at,
            },
        )
    if action == "PUBLISH":
        return (
            {**common, "status": "ACADEMIC_REVIEW", "publishAt": None},
            {
                **common,
                "status": "PUBLISHED",
                "publishAt": task.publish_at,
                "academicReviewerId": int(task.academic_reviewer_id) if task.academic_reviewer_id else None,
                "academicReviewedAt": task.academic_reviewed_at,
            },
        )
    if action == "ACADEMIC_RETURN":
        return (
            {**common, "status": "ACADEMIC_REVIEW"},
            {**common, "status": "RETURNED", "returnReason": task.return_reason or ""},
        )
    if action == "ARCHIVE":
        return (
            {**common, "status": "PUBLISHED"},
            {**common, "status": "ARCHIVED"},
        )
    return None, None


def _record_state(rec):
    return {
        "recordId": int(rec.id),
        "taskId": int(rec.task_id) if rec.task_id else None,
        "studentId": int(rec.student_id) if rec.student_id else None,
        "usualScore": rec.usual_score,
        "midtermScore": getattr(rec, "midterm_score", None),
        "finalScore": rec.final_score,
        "totalScore": rec.total_score,
        "passStatus": rec.pass_status,
        "source": rec.source or "",
        "versionNo": rec.version_no,
    }


def _record_snapshots(db, record_id: int, action: str):
    from app.models import AaGradeRecord, AffairsAuditTrail
    from app.services.db_service import _tid

    rec = db.get(AaGradeRecord, int(record_id))
    if not rec:
        return None, None

    current = _record_state(rec)
    original = {
        **current,
        "usualScore": rec.prev_usual_score,
        "midtermScore": getattr(rec, "prev_midterm_score", None),
        "finalScore": rec.prev_final_score,
        "totalScore": rec.prev_total_score,
        "source": "PUBLISH" if (rec.source or "") == "CHANGE" else (rec.source or ""),
        "versionNo": max(1, int(rec.version_no or 1) - (1 if action == "CHANGE_APPROVE" else 0)),
    }

    if action == "CHANGE_APPLY":
        return (
            {**original, "changeStatus": "PUBLISHED"},
            {**current, "changeStatus": "CHANGE_REVIEW", "changeReason": rec.change_reason or ""},
        )
    if action == "CHANGE_STEP":
        return (
            {**current, "changeNode": "COLLEGE_REVIEW"},
            {**current, "changeNode": "ACADEMIC_REVIEW"},
        )
    if action == "CHANGE_APPROVE":
        return (
            {**original, "changeStatus": "CHANGE_REVIEW"},
            {**current, "changeStatus": "PUBLISHED", "changeAt": rec.change_at},
        )
    if action == "CHANGE_REJECT":
        # Rejection restores the record before canonical _audit() is called. Recover the proposed
        # state from the preceding CHANGE_APPLY evidence, then prove the after-state equals current.
        prior = db.scalars(
            select(AffairsAuditTrail)
            .where(
                AffairsAuditTrail.tenant_id == _tid(),
                AffairsAuditTrail.biz_type == "AA_GRADE_RECORD",
                AffairsAuditTrail.biz_id == int(record_id),
                AffairsAuditTrail.action == "CHANGE_APPLY",
            )
            .order_by(AffairsAuditTrail.id.desc())
        ).first()
        proposed = None
        if prior and (prior.after_val or "").strip():
            try:
                proposed = json.loads(prior.after_val)
            except (TypeError, ValueError, json.JSONDecodeError):
                proposed = {"raw": prior.after_val}
        return (
            proposed or {**current, "changeStatus": "CHANGE_REVIEW"},
            {**current, "changeStatus": "PUBLISHED", "rejected": True},
        )
    return None, None


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.models import AffairsAuditTrail
    from app.modules.academic_affairs.services import academic_affairs_grade_core_service as grade_svc

    original = grade_svc._audit
    if getattr(original, "__grade_evidence_guard__", False):
        _INSTALLED = True
        return

    def audited(db, biz_type, biz_id, action, detail="", *, before_val=None, after_val=None):
        high_risk = {
            "AA_GRADE_TASK": {
                "SUBMIT", "COLLEGE_RETURN", "COLLEGE_APPROVE", "PUBLISH", "ACADEMIC_RETURN", "ARCHIVE"
            },
            "AA_GRADE_RECORD": {"CHANGE_APPLY", "CHANGE_STEP", "CHANGE_APPROVE", "CHANGE_REJECT"},
        }
        if action not in high_risk.get(biz_type, set()):
            return original(db, biz_type, biz_id, action, detail)

        if before_val is None and after_val is None and biz_id:
            if biz_type == "AA_GRADE_TASK":
                before_val, after_val = _task_snapshots(db, int(biz_id), action)
            elif biz_type == "AA_GRADE_RECORD":
                before_val, after_val = _record_snapshots(db, int(biz_id), action)

        name, role, uid = grade_svc._op()
        db.add(
            AffairsAuditTrail(
                tenant_id=grade_svc._tid(),
                biz_type=biz_type,
                biz_id=int(biz_id) if biz_id else None,
                action=action,
                operator=name or uid,
                role_name=role,
                detail=detail,
                before_val=_json(before_val),
                after_val=_json(after_val),
                occurred_at=datetime.utcnow(),
            )
        )

    audited.__grade_evidence_guard__ = True
    grade_svc._audit = audited
    _INSTALLED = True
