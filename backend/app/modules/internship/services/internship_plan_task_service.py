"""岗位实习计划任务完成度：学生按当前计划提交，导师按版本确认。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_,case,func,or_,select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipAuditTrail, InternshipBatchPlan, InternshipPlanAck, InternshipPlanAssignment,
    InternshipPlanTaskProgress, InternshipRecord, StudentProfile,
)
from app.services.db_service import _as_id, _iso, _tid, session

PROG_LABEL = {
    "NOT_STARTED": "未开始",
    "SUBMITTED": "待确认",
    "APPROVED": "已完成",
    "REJECTED": "已退回",
}


def _op_name(user=None) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, pid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=pid, target_type="PLAN_TASK",
        action=action, operator_name=operator, detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _expected(raw, current: int) -> None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException("DATA_CONFLICT", "缺少有效任务版本，请刷新后重试")
    if value != int(current or 0):
        raise AppException("DATA_CONFLICT", "任务已被其他用户处理，请刷新后重试")


def _validate_file(file_id) -> str | None:
    fid = str(file_id or "").strip()
    if not fid:
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "任务凭证不存在或无权访问，请重新上传")
    return fid


def _row(prog, rec=None, stu=None, batch_id=None):
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
        "version": int(prog.version or 0),
    }


def init_progress_for_plan(db, plan: InternshipBatchPlan, recs: list) -> int:
    """计划发布后为每生×每任务生成 NOT_STARTED 记录（幂等）。"""
    tasks = plan.tasks_json or []
    if not tasks:
        return 0
    created = 0
    for rec in recs:
        for task in tasks:
            sort_order = int(task.get("sortOrder") or 0)
            if not sort_order:
                continue
            duplicate = db.scalar(select(InternshipPlanTaskProgress).where(
                InternshipPlanTaskProgress.tenant_id == _tid(),
                InternshipPlanTaskProgress.plan_id == plan.id,
                InternshipPlanTaskProgress.internship_id == rec.id,
                InternshipPlanTaskProgress.task_sort_order == sort_order,
                InternshipPlanTaskProgress.is_deleted.is_(False)))
            if duplicate:
                continue
            db.add(InternshipPlanTaskProgress(
                tenant_id=_tid(), plan_id=plan.id, internship_id=rec.id,
                student_id=rec.student_id, task_sort_order=sort_order,
                task_name=(task.get("name") or f"任务{sort_order}").strip()[:100],
                status="NOT_STARTED"))
            created += 1
    return created


def _merge_tasks_with_progress(plan, progress_rows):
    progress_map = {row.task_sort_order: row for row in progress_rows}
    result = []
    for task in plan.tasks_json or []:
        sort_order = int(task.get("sortOrder") or 0)
        progress = progress_map.get(sort_order)
        result.append({
            **task,
            "progressId": str(progress.id) if progress else "",
            "progressStatus": progress.status if progress else "NOT_STARTED",
            "progressStatusLabel": PROG_LABEL.get(
                progress.status if progress else "NOT_STARTED"),
            "studentNote": progress.student_note if progress else "",
            "evidenceFileId": progress.evidence_file_id if progress else "",
            "submittedAt": _iso(progress.submitted_at) if progress and progress.submitted_at else "",
            "reviewComment": progress.review_comment if progress else "",
            "progressVersion": int(progress.version or 0) if progress else 0,
        })
    return result


def _student_current_context(db, user, *, plan_id=None, batch_id=None, internship_id=None, lock=False):
    from app.modules.internship.services import internship_plan_service as plan_service

    record, student = plan_service._student_plan_record(
        db, user, batch_id=batch_id, internship_id=internship_id, for_write=lock)
    if not record:
        return record, student, None, None
    plan, _assignment = plan_service._student_plan_for_record(
        db, record, plan_id, lock=lock)
    if not plan:
        return record, student, None, None
    ack_query = select(InternshipPlanAck).where(
        InternshipPlanAck.tenant_id == _tid(),
        InternshipPlanAck.plan_id == plan.id,
        InternshipPlanAck.internship_id == record.id,
        InternshipPlanAck.is_deleted.is_(False))
    ack = db.scalar(ack_query.with_for_update() if lock else ack_query)
    return record, student, plan, ack


def student_tasks(user, plan_id=None, batch_id=None, internship_id=None) -> dict:
    with session() as db:
        record, _student, plan, ack = _student_current_context(
            db, user, plan_id=plan_id, batch_id=batch_id, internship_id=internship_id)
        if not record or not plan:
            return {
                "planId": "", "planVersion": 0, "ackId": "", "ackStatus": "PENDING",
                "ackVersion": 0, "tasks": [], "summary": {"total": 0, "approved": 0, "rate": 0},
            }
        rows = db.scalars(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(),
            InternshipPlanTaskProgress.plan_id == plan.id,
            InternshipPlanTaskProgress.internship_id == record.id,
            InternshipPlanTaskProgress.is_deleted.is_(False))).all()
        if not rows and (plan.tasks_json or []):
            init_progress_for_plan(db, plan, [record])
            db.commit()
            rows = db.scalars(select(InternshipPlanTaskProgress).where(
                InternshipPlanTaskProgress.tenant_id == _tid(),
                InternshipPlanTaskProgress.plan_id == plan.id,
                InternshipPlanTaskProgress.internship_id == record.id,
                InternshipPlanTaskProgress.is_deleted.is_(False))).all()
        tasks = _merge_tasks_with_progress(plan, rows)
        from app.modules.internship.services import internship_report_quality_service as quality
        rules = quality.rules_for_batch(db, plan.batch_id)
        minimum_words = int(rules.get("planTaskMinWords") or 10)
        total = len(tasks)
        approved = sum(1 for task in tasks if task.get("progressStatus") == "APPROVED")
        return {
            "planId": str(plan.id), "planVersion": int(plan.version or 0),
            "context": {"batchId": str(record.batch_id), "internshipId": str(record.id)},
            "planBatchId": str(plan.batch_id),
            "planTitle": plan.title,
            "minimumWords": minimum_words,
            "ackId": str(ack.id) if ack else "", "ackStatus": ack.status if ack else "PENDING",
            "ackVersion": int(ack.version or 0) if ack else 0,
            "tasks": tasks,
            "summary": {
                "total": total, "approved": approved,
                "rate": round(approved * 100 / total) if total else 0,
            },
        }


def student_submit_task(user, sort_order: int, body: dict) -> dict:
    payload = body or {}
    try:
        sort_order = int(sort_order)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "任务序号无效")
    note = str(payload.get("studentNote") or payload.get("note") or "").strip()
    evidence_file_id = _validate_file(
        payload.get("evidenceFileId") or payload.get("fileId"))
    with session() as db:
        record, _student, plan, ack = _student_current_context(
            db, user, plan_id=payload.get("planId"), batch_id=payload.get("batchId"),
            internship_id=payload.get("internshipId"), lock=True)
        if not record or not plan:
            raise AppException("DATA_NOT_FOUND", "当前批次没有已发布实习计划")
        from app.modules.internship.services import internship_report_quality_service as quality
        rules = quality.rules_for_batch(db, plan.batch_id)
        minimum = int(rules.get("planTaskMinWords") or 10)
        if len(note) < minimum:
            raise AppException("VALIDATION_ERROR", f"完成说明至少 {minimum} 字")
        if not ack or ack.status != "ACKNOWLEDGED":
            raise AppException("DATA_CONFLICT", "请先确认当前版本实习计划后再提交任务")
        if payload.get("planId") and str(payload.get("planId")) != str(plan.id):
            raise AppException("DATA_CONFLICT", "计划版本已变化，请刷新后重新办理")
        progress = db.scalar(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(),
            InternshipPlanTaskProgress.plan_id == plan.id,
            InternshipPlanTaskProgress.internship_id == record.id,
            InternshipPlanTaskProgress.task_sort_order == sort_order,
            InternshipPlanTaskProgress.is_deleted.is_(False)).with_for_update())
        if not progress:
            raise not_found("当前计划任务不存在")
        _expected(payload.get("expectedVersion"), progress.version)
        if progress.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "该任务已确认完成")
        if progress.status == "SUBMITTED":
            raise AppException("DATA_CONFLICT", "该任务已提交，正在等待教师确认")
        progress.status = "SUBMITTED"
        progress.student_note = note[:500]
        progress.evidence_file_id = evidence_file_id
        progress.submitted_at = datetime.utcnow()
        progress.reviewed_by_name = None
        progress.reviewed_at = None
        progress.review_comment = None
        progress.version = int(progress.version or 0) + 1
        _trail(db, progress.id, "STUDENT_SUBMIT_VERSIONED", {
            "planId": str(plan.id), "sortOrder": sort_order,
            "hasEvidence": bool(evidence_file_id),
            "minimumWords": minimum,
            "newVersion": int(progress.version or 0),
        }, _op_name(user))
        db.commit()
        return _row(progress, record, _student, batch_id=plan.batch_id)


def _progress_query(user=None, batch_id=None):
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    p,r,s,plan = InternshipPlanTaskProgress,InternshipRecord,StudentProfile,InternshipBatchPlan
    visible = apply_internship_record_scope(select(r.id).where(
        r.tenant_id == _tid(), r.is_deleted.is_(False)),user).subquery()
    active_assignment = select(InternshipPlanAssignment.id).where(
        InternshipPlanAssignment.tenant_id == _tid(), InternshipPlanAssignment.internship_id == p.internship_id,
        InternshipPlanAssignment.plan_id == p.plan_id, InternshipPlanAssignment.status == "ACTIVE",
        InternshipPlanAssignment.is_deleted.is_(False)).correlate(p).exists()
    legacy_primary = r.batch_id == plan.batch_id
    query = select(p,r,s,plan).select_from(p).join(r,and_(r.id == p.internship_id,r.tenant_id == _tid(),r.is_deleted.is_(False)))
    query = query.join(s,and_(s.id == r.student_id,s.id == p.student_id,s.tenant_id == _tid()))
    query = query.join(plan,and_(plan.id == p.plan_id,plan.tenant_id == _tid(),plan.is_deleted.is_(False)))
    query = query.where(p.tenant_id == _tid(),p.is_deleted.is_(False),r.id.in_(select(visible.c.id)),or_(active_assignment,legacy_primary))
    if batch_id:
        try:
            query = query.where(plan.batch_id == int(batch_id))
        except (TypeError,ValueError):
            raise AppException("VALIDATION_ERROR","实习批次编号无效") from None
    return query


def list_progress(page, page_size, batch_id=None, status=None, keyword=None,
                  task_sort_order=None, user=None):
    p,s = InternshipPlanTaskProgress,StudentProfile
    with session() as db:
        query = _progress_query(user,batch_id)
        if status:
            query = query.where(p.status == status)
        if task_sort_order is not None:
            query = query.where(p.task_sort_order == int(task_sort_order))
        if keyword and keyword.strip():
            query = query.where(or_(s.real_name.contains(keyword.strip(),autoescape=True),s.student_no.contains(keyword.strip(),autoescape=True)))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = db.execute(query.order_by(p.id.desc()).offset((max(1,page)-1)*page_size).limit(page_size)).all()
        items=[]
        for progress,record,student,plan in rows:
            task = next((t for t in plan.tasks_json or [] if int(t.get('sortOrder') or 0) == progress.task_sort_order),{})
            items.append({**_row(progress,record,student,batch_id=plan.batch_id),
                'planTitle':plan.title,'planBatchId':str(plan.batch_id),
                'taskRequirement':task.get('requirement') or '', 'taskDeadline':task.get('deadline') or ''})
        return items,total


def review_progress(prog_id, action: str, comment: str = "", user=None,
                    *, expected_version=None, expected_batch_id=None) -> dict:
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE 或 REJECT")
    if action == "REJECT" and len(str(comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因至少5个字")
    with session() as db:
        progress = db.scalar(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.id == _as_id(prog_id),
            InternshipPlanTaskProgress.tenant_id == _tid(),
            InternshipPlanTaskProgress.is_deleted.is_(False)).with_for_update())
        if not progress:
            raise not_found("任务进度不存在")
        record = db.get(InternshipRecord, progress.internship_id)
        student = db.get(StudentProfile, progress.student_id)
        if not _rec_in_scope(_current_scope(user), db, record, student):
            raise no_permission("只能处理本人指导学生的任务完成确认")
        plan = db.get(InternshipBatchPlan, progress.plan_id)
        if not plan or plan.is_deleted or plan.tenant_id != _tid():
            raise AppException("DATA_CONFLICT", "任务所属实习方案不存在")
        if expected_batch_id not in (None, ""):
            try:
                expected_plan_batch = int(expected_batch_id)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "batchId 格式非法") from None
            if int(plan.batch_id or 0) != expected_plan_batch:
                raise AppException("DATA_CONFLICT", "任务不属于当前选择的实习方案批次，请刷新")
        _expected(expected_version, progress.version)
        if progress.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅待确认任务可批阅")
        progress.status = "APPROVED" if action == "APPROVE" else "REJECTED"
        progress.review_comment = str(comment or "").strip() or None
        progress.reviewed_by_name = _op_name(user)
        progress.reviewed_at = datetime.utcnow()
        progress.version = int(progress.version or 0) + 1
        _trail(db, progress.id, f"REVIEW_{action}_VERSIONED", {
            "comment": progress.review_comment,
            "newVersion": int(progress.version or 0),
        }, _op_name(user))
        db.commit()
        return _row(progress, record, student, batch_id=plan.batch_id)


def batch_summary(batch_id, user=None) -> dict:
    with session() as db:
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == int(batch_id),
            InternshipBatchPlan.is_deleted.is_(False)))
        if not plan:
            return {"totalTasks": 0, "studentCount": 0, "avgRate": 0, "pendingReview": 0}
        p = InternshipPlanTaskProgress
        aggregates = db.execute(_progress_query(user,batch_id).with_only_columns(
            p.student_id,func.count().label('total'),
            func.sum(case((p.status == 'APPROVED',1),else_=0)).label('approved'),
            func.sum(case((p.status == 'SUBMITTED',1),else_=0)).label('pending'))
            .group_by(p.student_id)).all()
        rates = [round(row.approved*100/row.total) for row in aggregates if row.total]
        return {
            "totalTasks": len(plan.tasks_json or []),
            "studentCount": len(aggregates),
            "avgRate": round(sum(rates) / len(rates)) if rates else 0,
            "pendingReview": sum(int(row.pending) for row in aggregates),
        }
