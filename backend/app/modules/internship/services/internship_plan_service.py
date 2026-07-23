"""岗位实习 · 批次实习计划书（编制/发布/下发/学生确认）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipBatch, InternshipBatchPlan,
                        InternshipPlanAck, InternshipRecord, StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"DRAFT": "草稿", "PUBLISHED": "已发布"}
ACK_LABEL = {"PENDING": "待确认", "ACKNOWLEDGED": "已确认"}


def _normalize_tasks(raw) -> list:
    """任务清单 [{sortOrder, name, requirement, deadline}]。"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "tasks 必须是数组")
    if len(raw) > 50:
        raise AppException("VALIDATION_ERROR", "任务清单最多 50 条")
    out = []
    for i, t in enumerate(raw):
        if not isinstance(t, dict):
            raise AppException("VALIDATION_ERROR", f"任务第 {i + 1} 项格式错误")
        name = (t.get("name") or "").strip()
        req = (t.get("requirement") or "").strip()
        deadline = (t.get("deadline") or "").strip() or None
        if not name and not req and not deadline:
            continue
        if len(name) < 2:
            raise AppException("VALIDATION_ERROR", f"任务第 {i + 1} 项名称至少 2 字")
        if len(name) > 100:
            raise AppException("VALIDATION_ERROR", f"任务第 {i + 1} 项名称过长")
        if req and len(req) > 500:
            raise AppException("VALIDATION_ERROR", f"任务第 {i + 1} 项要求过长")
        sort_order = t.get("sortOrder")
        if sort_order is None:
            sort_order = i + 1
        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", f"任务第 {i + 1} 项序号无效")
        out.append({
            "sortOrder": sort_order,
            "name": name,
            "requirement": req or None,
            "deadline": deadline,
        })
    return sorted(out, key=lambda x: x["sortOrder"])


def _op_name(user=None) -> str:
    if user:
        return user.get("realName") or "系统"
    return "系统"


def _trail(db, pid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=pid, target_type="BATCH_PLAN",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _plan_row(p, batch=None):
    return {
        "id": str(p.id), "batchId": str(p.batch_id),
        "batchName": batch.batch_name if batch else "",
        "title": p.title, "objectives": p.objectives or "", "content": p.content or "",
        "tasks": p.tasks_json or [],
        "status": p.status, "statusLabel": STATUS_LABEL.get(p.status, p.status),
        "publishedAt": _iso(p.published_at) or "",
        "publishedByName": p.published_by_name or "",
    }


def get_plan_by_batch(batch_id, user=None):
    with session() as db:
        b = db.get(InternshipBatch, _as_id(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("批次不存在")
        p = db.scalars(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(), InternshipBatchPlan.batch_id == b.id,
            InternshipBatchPlan.is_deleted.is_(False))).first()
        if not p:
            return None
        return _plan_row(p, b)


def save_plan(batch_id, body, user=None) -> dict:
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "保存实习计划书")
    b = body or {}
    title = (b.get("title") or "").strip()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "计划标题必填")
    content = (b.get("content") or "").strip()
    if len(content) < 20:
        raise AppException("VALIDATION_ERROR", "计划正文至少 20 字")
    with session() as db:
        batch = db.get(InternshipBatch, _as_id(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("批次不存在")
        p = db.scalars(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(), InternshipBatchPlan.batch_id == batch.id,
            InternshipBatchPlan.is_deleted.is_(False))).first()
        if p and p.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "已发布计划不可直接编辑，请先撤回发布")
        if not p:
            p = InternshipBatchPlan(tenant_id=_tid(), batch_id=batch.id, title=title, status="DRAFT")
            db.add(p)
        p.title = title
        p.objectives = (b.get("objectives") or "").strip() or None
        p.content = content
        p.tasks_json = _normalize_tasks(b.get("tasks"))
        db.flush()
        _trail(db, p.id, "SAVE", {"batchId": str(batch.id)}, _op_name(user))
        db.commit()
        return _plan_row(p, batch)


def publish_plan(batch_id, user=None) -> dict:
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "发布实习计划书")
    with session() as db:
        batch = db.get(InternshipBatch, _as_id(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("批次不存在")
        p = db.scalars(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(), InternshipBatchPlan.batch_id == batch.id,
            InternshipBatchPlan.is_deleted.is_(False))).first()
        if not p:
            raise not_found("请先保存实习计划书")
        if p.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "计划已发布")
        p.status = "PUBLISHED"
        p.published_at = datetime.utcnow()
        p.published_by_name = _op_name(user)
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False))).all()
        ack_count = 0
        for rec in recs:
            dup = db.scalars(select(InternshipPlanAck).where(
                InternshipPlanAck.tenant_id == _tid(), InternshipPlanAck.plan_id == p.id,
                InternshipPlanAck.internship_id == rec.id, InternshipPlanAck.is_deleted.is_(False))).first()
            if dup:
                if dup.status == "PENDING":
                    ack_count += 1
                continue
            db.add(InternshipPlanAck(tenant_id=_tid(), plan_id=p.id, internship_id=rec.id,
                                     student_id=rec.student_id, status="PENDING"))
            ack_count += 1
        from app.modules.internship.services.internship_plan_task_service import init_progress_for_plan
        task_prog_count = init_progress_for_plan(db, p, recs)
        _trail(db, p.id, "PUBLISH", {"ackCount": ack_count, "taskProgressInit": task_prog_count},
               _op_name(user))
        db.commit()
        return {**_plan_row(p, batch), "ackCount": ack_count, "taskProgressInit": task_prog_count}


def list_acks(page, page_size, batch_id=None, status=None, keyword=None, user=None):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    scope, in_scope = _current_scope(user), _rec_in_scope
    with session() as db:
        q = select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(), InternshipPlanAck.is_deleted.is_(False))
        if status:
            q = q.where(InternshipPlanAck.status == status)
        rows = db.scalars(q.order_by(InternshipPlanAck.id.desc())).all()
        items = []
        for ack in rows:
            rec = db.get(InternshipRecord, ack.internship_id)
            stu = db.get(StudentProfile, ack.student_id)
            plan = db.get(InternshipBatchPlan, ack.plan_id)
            if batch_id and (not rec or str(rec.batch_id) != str(batch_id)):
                continue
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append({
                "id": str(ack.id), "internId": str(ack.internship_id),
                "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
                "batchId": str(rec.batch_id) if rec and rec.batch_id else "",
                "planTitle": plan.title if plan else "",
                "status": ack.status, "statusLabel": ACK_LABEL.get(ack.status, ack.status),
                "acknowledgedAt": _iso(ack.acknowledged_at) or "",
            })
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def student_my_plan(user) -> dict | None:
    from app.modules.internship.services.internship_agreement_service import _student_record
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec or not rec.batch_id:
            return None
        p = db.scalars(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(), InternshipBatchPlan.batch_id == rec.batch_id,
            InternshipBatchPlan.status == "PUBLISHED", InternshipBatchPlan.is_deleted.is_(False))).first()
        if not p:
            return None
        ack = db.scalars(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(), InternshipPlanAck.plan_id == p.id,
            InternshipPlanAck.internship_id == rec.id, InternshipPlanAck.is_deleted.is_(False))).first()
        from app.models import InternshipPlanTaskProgress
        from app.modules.internship.services.internship_plan_task_service import PROG_LABEL, _merge_tasks_with_progress
        prog_rows = db.scalars(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(), InternshipPlanTaskProgress.plan_id == p.id,
            InternshipPlanTaskProgress.internship_id == rec.id,
            InternshipPlanTaskProgress.is_deleted.is_(False))).all()
        tasks = _merge_tasks_with_progress(p, prog_rows)
        total = len(tasks)
        approved = sum(1 for t in tasks if t.get("progressStatus") == "APPROVED")
        return {
            **_plan_row(p),
            "ackId": str(ack.id) if ack else "",
            "ackStatus": ack.status if ack else "PENDING",
            "ackStatusLabel": ACK_LABEL.get(ack.status if ack else "PENDING"),
            "acknowledgedAt": _iso(ack.acknowledged_at) if ack else "",
            "tasks": tasks,
            "taskSummary": {"total": total, "approved": approved,
                            "rate": round(approved * 100 / total) if total else 0},
        }


def student_acknowledge(user) -> dict:
    from app.modules.internship.services.internship_agreement_service import _student_record
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            raise not_found("未找到实习记录")
        ack = db.scalars(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(), InternshipPlanAck.internship_id == rec.id,
            InternshipPlanAck.status == "PENDING", InternshipPlanAck.is_deleted.is_(False))).first()
        if not ack:
            raise AppException("DATA_NOT_FOUND", "当前没有待确认的实习计划")
        ack.status = "ACKNOWLEDGED"
        ack.acknowledged_at = datetime.utcnow()
        _trail(db, ack.plan_id, "STUDENT_ACK", {"studentNo": stu.student_no if stu else ""},
               (user or {}).get("realName") or "学生")
        db.commit()
        return {"id": str(ack.id), "status": "ACKNOWLEDGED", "message": "已确认实习计划"}
