"""岗位实习 · 计划任务完成度（学生提交 / 导师确认）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipBatchPlan, InternshipPlanAck,
                        InternshipPlanTaskProgress, InternshipRecord, StudentProfile)
from app.services.db_service import _iso, _tid, session

PROG_LABEL = {
    "NOT_STARTED": "未开始",
    "SUBMITTED": "待确认",
    "APPROVED": "已完成",
    "REJECTED": "已退回",
}


def _op_name(user=None) -> str:
    if user:
        return user.get("realName") or "系统"
    return "系统"


def _trail(db, pid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=pid, target_type="PLAN_TASK",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _row(prog, rec=None, stu=None, batch_id=None):
    total_hint = None
    return {
        "id": str(prog.id),
        "planId": str(prog.plan_id),
        "internId": str(prog.internship_id),
        "studentId": str(prog.student_id),
        "studentName": stu.real_name if stu else "-",
        "studentNo": stu.student_no if stu else "-",
        "batchId": str(batch_id or (rec.batch_id if rec else "")),
        "taskSortOrder": prog.task_sort_order,
        "taskName": prog.task_name,
        "status": prog.status,
        "statusLabel": PROG_LABEL.get(prog.status, prog.status),
        "studentNote": prog.student_note or "",
        "evidenceFileId": prog.evidence_file_id or "",
        "submittedAt": _iso(prog.submitted_at) or "",
        "reviewedByName": prog.reviewed_by_name or "",
        "reviewedAt": _iso(prog.reviewed_at) or "",
        "reviewComment": prog.review_comment or "",
    }


def init_progress_for_plan(db, plan: InternshipBatchPlan, recs: list) -> int:
    """计划发布后为每生×每任务生成 NOT_STARTED 记录（幂等）。"""
    tasks = plan.tasks_json or []
    if not tasks:
        return 0
    created = 0
    for rec in recs:
        for t in tasks:
            sort_order = int(t.get("sortOrder") or 0)
            if not sort_order:
                continue
            dup = db.scalars(select(InternshipPlanTaskProgress).where(
                InternshipPlanTaskProgress.tenant_id == _tid(),
                InternshipPlanTaskProgress.plan_id == plan.id,
                InternshipPlanTaskProgress.internship_id == rec.id,
                InternshipPlanTaskProgress.task_sort_order == sort_order,
                InternshipPlanTaskProgress.is_deleted.is_(False))).first()
            if dup:
                continue
            db.add(InternshipPlanTaskProgress(
                tenant_id=_tid(), plan_id=plan.id, internship_id=rec.id,
                student_id=rec.student_id, task_sort_order=sort_order,
                task_name=(t.get("name") or f"任务{sort_order}").strip()[:100],
                status="NOT_STARTED"))
            created += 1
    return created


def _merge_tasks_with_progress(plan, progress_rows):
    prog_map = {p.task_sort_order: p for p in progress_rows}
    out = []
    for t in plan.tasks_json or []:
        sort_order = int(t.get("sortOrder") or 0)
        p = prog_map.get(sort_order)
        out.append({
            **t,
            "progressId": str(p.id) if p else "",
            "progressStatus": p.status if p else "NOT_STARTED",
            "progressStatusLabel": PROG_LABEL.get(p.status if p else "NOT_STARTED"),
            "studentNote": p.student_note if p else "",
            "submittedAt": _iso(p.submitted_at) if p and p.submitted_at else "",
            "reviewComment": p.review_comment if p else "",
        })
    return out


def student_tasks(user) -> dict:
    from app.services.internship_agreement_service import _student_record
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec or not rec.batch_id:
            return {"tasks": [], "summary": {"total": 0, "approved": 0, "rate": 0}}
        plan = db.scalars(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(), InternshipBatchPlan.batch_id == rec.batch_id,
            InternshipBatchPlan.status == "PUBLISHED", InternshipBatchPlan.is_deleted.is_(False))).first()
        if not plan:
            return {"tasks": [], "summary": {"total": 0, "approved": 0, "rate": 0}}
        ack = db.scalars(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(), InternshipPlanAck.plan_id == plan.id,
            InternshipPlanAck.internship_id == rec.id, InternshipPlanAck.is_deleted.is_(False))).first()
        rows = db.scalars(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(), InternshipPlanTaskProgress.plan_id == plan.id,
            InternshipPlanTaskProgress.internship_id == rec.id,
            InternshipPlanTaskProgress.is_deleted.is_(False))).all()
        if not rows and (plan.tasks_json or []):
            init_progress_for_plan(db, plan, [rec])
            db.commit()
            rows = db.scalars(select(InternshipPlanTaskProgress).where(
                InternshipPlanTaskProgress.tenant_id == _tid(), InternshipPlanTaskProgress.plan_id == plan.id,
                InternshipPlanTaskProgress.internship_id == rec.id,
                InternshipPlanTaskProgress.is_deleted.is_(False))).all()
        tasks = _merge_tasks_with_progress(plan, rows)
        total = len(tasks)
        approved = sum(1 for t in tasks if t.get("progressStatus") == "APPROVED")
        rate = round(approved * 100 / total) if total else 0
        return {
            "planId": str(plan.id),
            "ackStatus": ack.status if ack else "PENDING",
            "tasks": tasks,
            "summary": {"total": total, "approved": approved, "rate": rate},
        }


def student_submit_task(user, sort_order: int, body: dict) -> dict:
    from app.services.internship_agreement_service import _student_record
    sort_order = int(sort_order)
    note = (body.get("studentNote") or body.get("note") or "").strip()
    if len(note) < 5:
        raise AppException("VALIDATION_ERROR", "完成说明至少 5 字")
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            raise not_found("未找到实习记录")
        ack = db.scalars(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(), InternshipPlanAck.internship_id == rec.id,
            InternshipPlanAck.status == "ACKNOWLEDGED", InternshipPlanAck.is_deleted.is_(False))).first()
        if not ack:
            raise AppException("DATA_CONFLICT", "请先确认实习计划书后再提交任务完成")
        prog = db.scalars(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(), InternshipPlanTaskProgress.internship_id == rec.id,
            InternshipPlanTaskProgress.task_sort_order == sort_order,
            InternshipPlanTaskProgress.is_deleted.is_(False))).first()
        if not prog:
            raise not_found("任务不存在")
        if prog.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "该任务已确认完成")
        if prog.status == "SUBMITTED":
            raise AppException("DATA_CONFLICT", "该任务待教师确认，请勿重复提交")
        prog.status = "SUBMITTED"
        prog.student_note = note[:500]
        prog.evidence_file_id = (body.get("evidenceFileId") or body.get("fileId") or "").strip() or None
        prog.submitted_at = datetime.utcnow()
        _trail(db, prog.id, "STUDENT_SUBMIT", {"sortOrder": sort_order}, _op_name(user))
        db.commit()
        return {"id": str(prog.id), "status": prog.status, "statusLabel": PROG_LABEL[prog.status]}


def list_progress(page, page_size, batch_id=None, status=None, keyword=None, task_sort_order=None, user=None):
    from app.services.internship_service import _current_scope, _rec_in_scope
    scope, in_scope = _current_scope(user), _rec_in_scope
    with session() as db:
        q = select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(),
            InternshipPlanTaskProgress.is_deleted.is_(False))
        if status:
            q = q.where(InternshipPlanTaskProgress.status == status)
        if task_sort_order is not None:
            q = q.where(InternshipPlanTaskProgress.task_sort_order == int(task_sort_order))
        rows = db.scalars(q.order_by(InternshipPlanTaskProgress.id.desc())).all()
        items = []
        for prog in rows:
            rec = db.get(InternshipRecord, prog.internship_id)
            stu = db.get(StudentProfile, prog.student_id)
            if batch_id and (not rec or str(rec.batch_id) != str(batch_id)):
                continue
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")
                            and keyword.strip() not in (stu.student_no or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(prog, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def review_progress(prog_id, action: str, comment: str = "", user=None) -> dict:
    from app.services.internship_service import _current_scope, _rec_in_scope
    action = (action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE 或 REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因至少 5 字")
    scope, in_scope = _current_scope(user), _rec_in_scope
    with session() as db:
        prog = db.get(InternshipPlanTaskProgress, int(prog_id))
        if not prog or prog.is_deleted or prog.tenant_id != _tid():
            raise not_found("任务进度不存在")
        rec = db.get(InternshipRecord, prog.internship_id)
        stu = db.get(StudentProfile, prog.student_id)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能处理本人指导学生的任务完成确认")
        if prog.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅待确认状态可批阅")
        now = datetime.utcnow()
        op = _op_name(user)
        if action == "APPROVE":
            prog.status = "APPROVED"
            prog.review_comment = (comment or "").strip() or None
        else:
            prog.status = "REJECTED"
            prog.review_comment = comment.strip()
        prog.reviewed_by_name = op
        prog.reviewed_at = now
        _trail(db, prog.id, f"REVIEW_{action}", {"comment": prog.review_comment}, op)
        db.commit()
        return _row(prog, rec, stu)


def batch_summary(batch_id, user=None) -> dict:
    from app.services.internship_service import _current_scope, _rec_in_scope
    scope, in_scope = _current_scope(user), _rec_in_scope
    with session() as db:
        plan = db.scalars(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(), InternshipBatchPlan.batch_id == int(batch_id),
            InternshipBatchPlan.is_deleted.is_(False))).first()
        if not plan:
            return {"totalTasks": 0, "studentCount": 0, "avgRate": 0, "pendingReview": 0}
        rows = db.scalars(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(), InternshipPlanTaskProgress.plan_id == plan.id,
            InternshipPlanTaskProgress.is_deleted.is_(False))).all()
        by_student = {}
        pending = 0
        for prog in rows:
            rec = db.get(InternshipRecord, prog.internship_id)
            stu = db.get(StudentProfile, prog.student_id)
            if not in_scope(scope, db, rec, stu):
                continue
            sid = prog.student_id
            by_student.setdefault(sid, {"total": 0, "approved": 0})
            by_student[sid]["total"] += 1
            if prog.status == "APPROVED":
                by_student[sid]["approved"] += 1
            if prog.status == "SUBMITTED":
                pending += 1
        rates = [round(v["approved"] * 100 / v["total"]) for v in by_student.values() if v["total"]]
        avg = round(sum(rates) / len(rates)) if rates else 0
        return {
            "totalTasks": len(plan.tasks_json or []),
            "studentCount": len(by_student),
            "avgRate": avg,
            "pendingReview": pending,
        }
