"""岗位实习批次计划书：草稿编制、版本化发布、学生本人确认。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipAuditTrail, InternshipBatch, InternshipBatchPlan,
    InternshipPlanAck, InternshipRecord, StudentProfile,
)
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"DRAFT": "草稿", "PUBLISHED": "已发布"}
ACK_LABEL = {"PENDING": "待确认", "ACKNOWLEDGED": "已确认"}


def _normalize_tasks(raw) -> list:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "tasks 必须是数组")
    if len(raw) > 50:
        raise AppException("VALIDATION_ERROR", "任务清单最多50条")
    result = []
    used_orders = set()
    for index, task in enumerate(raw):
        if not isinstance(task, dict):
            raise AppException("VALIDATION_ERROR", f"任务第{index + 1}项格式错误")
        name = str(task.get("name") or "").strip()
        requirement = str(task.get("requirement") or "").strip()
        deadline = str(task.get("deadline") or "").strip() or None
        if not name and not requirement and not deadline:
            continue
        if not 2 <= len(name) <= 100:
            raise AppException("VALIDATION_ERROR", f"任务第{index + 1}项名称须为2至100字")
        if len(requirement) > 500:
            raise AppException("VALIDATION_ERROR", f"任务第{index + 1}项要求过长")
        try:
            sort_order = int(task.get("sortOrder") if task.get("sortOrder") is not None else index + 1)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", f"任务第{index + 1}项序号无效")
        if sort_order <= 0 or sort_order in used_orders:
            raise AppException("VALIDATION_ERROR", "任务序号必须为不重复的正整数")
        used_orders.add(sort_order)
        result.append({
            "sortOrder": sort_order,
            "name": name,
            "requirement": requirement or None,
            "deadline": deadline,
        })
    return sorted(result, key=lambda item: item["sortOrder"])


def _op_name(user=None) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, plan_id, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=plan_id, target_type="BATCH_PLAN",
        action=action, operator_name=operator, detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _expected(raw, current: int, label="计划") -> None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException("DATA_CONFLICT", f"缺少有效{label}版本，请刷新后重试")
    if value != int(current or 0):
        raise AppException("DATA_CONFLICT", f"{label}已被其他用户修改，请刷新后重试")


def _plan_row(plan, batch=None):
    return {
        "id": str(plan.id), "batchId": str(plan.batch_id),
        "batchName": batch.batch_name if batch else "",
        "title": plan.title, "objectives": plan.objectives or "",
        "content": plan.content or "", "tasks": plan.tasks_json or [],
        "status": plan.status, "statusLabel": STATUS_LABEL.get(plan.status, plan.status),
        "publishedAt": _iso(plan.published_at) or "",
        "publishedByName": plan.published_by_name or "",
        "version": int(plan.version or 0),
    }


def get_plan_by_batch(batch_id, user=None):
    with session() as db:
        batch = db.get(InternshipBatch, _as_id(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("批次不存在")
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == batch.id,
            InternshipBatchPlan.is_deleted.is_(False)))
        return _plan_row(plan, batch) if plan else None


def save_plan(batch_id, body, user=None) -> dict:
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "保存实习计划书")
    payload = body or {}
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "计划标题不少于2字")
    if len(content) < 20:
        raise AppException("VALIDATION_ERROR", "计划正文至少20字")
    tasks = _normalize_tasks(payload.get("tasks"))
    if not tasks:
        raise AppException("VALIDATION_ERROR", "至少配置1项可执行计划任务")
    with session() as db:
        batch = db.scalar(select(InternshipBatch).where(
            InternshipBatch.id == _as_id(batch_id),
            InternshipBatch.tenant_id == _tid(),
            InternshipBatch.is_deleted.is_(False)).with_for_update())
        if not batch:
            raise not_found("批次不存在")
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == batch.id,
            InternshipBatchPlan.is_deleted.is_(False)).with_for_update())
        if plan and plan.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "已发布计划不可直接编辑；请通过新批次或正式版本变更流程处理")
        if plan:
            _expected(payload.get("expectedVersion"), plan.version)
        else:
            plan = InternshipBatchPlan(
                tenant_id=_tid(), batch_id=batch.id, title=title, status="DRAFT")
            db.add(plan)
        plan.title = title
        plan.objectives = str(payload.get("objectives") or "").strip() or None
        plan.content = content
        plan.tasks_json = tasks
        plan.version = int(plan.version or 0) + 1
        db.flush()
        _trail(db, plan.id, "SAVE_VERSIONED", {
            "batchId": str(batch.id), "taskCount": len(tasks),
            "newVersion": int(plan.version or 0),
        }, _op_name(user))
        db.commit()
        return _plan_row(plan, batch)


def publish_plan(batch_id, body=None, user=None) -> dict:
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "发布实习计划书")
    payload = body or {}
    with session() as db:
        batch = db.scalar(select(InternshipBatch).where(
            InternshipBatch.id == _as_id(batch_id),
            InternshipBatch.tenant_id == _tid(),
            InternshipBatch.is_deleted.is_(False)).with_for_update())
        if not batch:
            raise not_found("批次不存在")
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == batch.id,
            InternshipBatchPlan.is_deleted.is_(False)).with_for_update())
        if not plan:
            raise not_found("请先保存实习计划书")
        _expected(payload.get("expectedVersion"), plan.version)
        if plan.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "计划已发布")
        if not (plan.tasks_json or []):
            raise AppException("DATA_CONFLICT", "计划未配置任务清单，不能发布")
        plan.status = "PUBLISHED"
        plan.published_at = datetime.utcnow()
        plan.published_by_name = _op_name(user)
        plan.version = int(plan.version or 0) + 1
        records = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False))).all()
        ack_count = 0
        for record in records:
            ack = db.scalar(select(InternshipPlanAck).where(
                InternshipPlanAck.tenant_id == _tid(),
                InternshipPlanAck.plan_id == plan.id,
                InternshipPlanAck.internship_id == record.id,
                InternshipPlanAck.is_deleted.is_(False)))
            if ack:
                if ack.status == "PENDING":
                    ack_count += 1
                continue
            db.add(InternshipPlanAck(
                tenant_id=_tid(), plan_id=plan.id, internship_id=record.id,
                student_id=record.student_id, status="PENDING"))
            ack_count += 1
        from app.modules.internship.services.internship_plan_task_service import init_progress_for_plan
        progress_count = init_progress_for_plan(db, plan, records)
        _trail(db, plan.id, "PUBLISH_VERSIONED", {
            "ackCount": ack_count, "taskProgressInit": progress_count,
            "newVersion": int(plan.version or 0),
        }, _op_name(user))
        db.commit()
        return {
            **_plan_row(plan, batch), "ackCount": ack_count,
            "taskProgressInit": progress_count,
        }


def list_acks(page, page_size, batch_id=None, status=None, keyword=None, user=None):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    scope, in_scope = _current_scope(user), _rec_in_scope
    with session() as db:
        query = select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(),
            InternshipPlanAck.is_deleted.is_(False))
        if status:
            query = query.where(InternshipPlanAck.status == status)
        rows = db.scalars(query.order_by(InternshipPlanAck.id.desc())).all()
        items = []
        for ack in rows:
            record = db.get(InternshipRecord, ack.internship_id)
            student = db.get(StudentProfile, ack.student_id)
            plan = db.get(InternshipBatchPlan, ack.plan_id)
            if batch_id and (not record or str(record.batch_id) != str(batch_id)):
                continue
            if keyword and (not student or keyword.strip() not in (student.real_name or "")):
                continue
            if not in_scope(scope, db, record, student):
                continue
            items.append({
                "id": str(ack.id), "internId": str(ack.internship_id),
                "studentName": student.real_name if student else "-",
                "studentNo": student.student_no if student else "-",
                "batchId": str(record.batch_id) if record and record.batch_id else "",
                "planId": str(plan.id) if plan else "",
                "planTitle": plan.title if plan else "",
                "planVersion": int(plan.version or 0) if plan else 0,
                "status": ack.status, "statusLabel": ACK_LABEL.get(ack.status, ack.status),
                "acknowledgedAt": _iso(ack.acknowledged_at) or "",
                "version": int(ack.version or 0),
            })
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def student_my_plan(user) -> dict | None:
    from app.modules.internship.services.internship_agreement_service import _student_record
    with session() as db:
        record, _student = _student_record(db, user)
        if not record or not record.batch_id:
            return None
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == record.batch_id,
            InternshipBatchPlan.status == "PUBLISHED",
            InternshipBatchPlan.is_deleted.is_(False)))
        if not plan:
            return None
        ack = db.scalar(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(),
            InternshipPlanAck.plan_id == plan.id,
            InternshipPlanAck.internship_id == record.id,
            InternshipPlanAck.is_deleted.is_(False)))
        from app.models import InternshipPlanTaskProgress
        from app.modules.internship.services.internship_plan_task_service import _merge_tasks_with_progress
        progress_rows = db.scalars(select(InternshipPlanTaskProgress).where(
            InternshipPlanTaskProgress.tenant_id == _tid(),
            InternshipPlanTaskProgress.plan_id == plan.id,
            InternshipPlanTaskProgress.internship_id == record.id,
            InternshipPlanTaskProgress.is_deleted.is_(False))).all()
        tasks = _merge_tasks_with_progress(plan, progress_rows)
        total = len(tasks)
        approved = sum(1 for task in tasks if task.get("progressStatus") == "APPROVED")
        return {
            **_plan_row(plan),
            "ackId": str(ack.id) if ack else "",
            "ackStatus": ack.status if ack else "PENDING",
            "ackStatusLabel": ACK_LABEL.get(ack.status if ack else "PENDING"),
            "ackVersion": int(ack.version or 0) if ack else 0,
            "acknowledgedAt": _iso(ack.acknowledged_at) if ack else "",
            "tasks": tasks,
            "taskSummary": {
                "total": total, "approved": approved,
                "rate": round(approved * 100 / total) if total else 0,
            },
        }


def student_acknowledge(user, body=None) -> dict:
    from app.modules.internship.services.internship_agreement_service import _student_record
    payload = body or {}
    with session() as db:
        if payload.get("batchId") is not None or payload.get("internshipId") is not None:
            from app.modules.internship.services.internship_student_context_guard import (
                require_explicit_context,
            )
            record, student, _batch_id = require_explicit_context(
                db, user, payload, for_write=True)
        else:
            record, student = _student_record(db, user, for_write=True)
        plan = db.scalar(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.batch_id == record.batch_id,
            InternshipBatchPlan.status == "PUBLISHED",
            InternshipBatchPlan.is_deleted.is_(False)).with_for_update())
        if not plan:
            raise AppException("DATA_NOT_FOUND", "当前批次没有已发布实习计划")
        ack = db.scalar(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(),
            InternshipPlanAck.plan_id == plan.id,
            InternshipPlanAck.internship_id == record.id,
            InternshipPlanAck.is_deleted.is_(False)).with_for_update())
        if not ack:
            raise AppException("DATA_NOT_FOUND", "当前没有待确认的实习计划回执")
        _expected(payload.get("planVersion"), plan.version, "计划正文")
        _expected(payload.get("expectedVersion"), ack.version, "确认回执")
        if ack.status != "PENDING":
            if ack.status == "ACKNOWLEDGED":
                return {
                    "id": str(ack.id), "status": ack.status,
                    "version": int(ack.version or 0), "message": "实习计划已确认",
                }
            raise AppException("DATA_CONFLICT", "当前计划回执不可确认")
        ack.status = "ACKNOWLEDGED"
        ack.acknowledged_at = datetime.utcnow()
        ack.version = int(ack.version or 0) + 1
        _trail(db, plan.id, "STUDENT_ACK_VERSIONED", {
            "studentNo": student.student_no if student else "",
            "planVersion": int(plan.version or 0),
            "newAckVersion": int(ack.version or 0),
        }, _op_name(user))
        db.commit()
        return {
            "id": str(ack.id), "status": ack.status,
            "version": int(ack.version or 0), "message": "已确认当前版本实习计划",
        }
