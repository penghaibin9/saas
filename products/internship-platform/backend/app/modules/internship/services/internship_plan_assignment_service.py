"""AP04 student multi-plan assignment authority.

A plan assignment links one canonical InternshipRecord to one published InternshipBatchPlan.
It does not duplicate plan content or internship facts.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipAuditTrail,
    InternshipBatch,
    InternshipBatchPlan,
    InternshipPlanAck,
    InternshipPlanAssignment,
    InternshipPlanTaskProgress,
    InternshipRecord,
    StudentProfile,
)
from app.modules.internship.services.internship_plan_task_service import init_progress_for_plan
from app.services.db_service import _as_id, _iso, _tid, session


def _operator(user=None) -> str:
    return (user or {}).get("realName") or "系统"


def _audit(db, assignment_id: int, action: str, detail: dict, user=None) -> None:
    db.add(InternshipAuditTrail(
        tenant_id=_tid(),
        target_id=int(assignment_id),
        target_type="PLAN_ASSIGNMENT",
        action=action,
        operator_name=_operator(user),
        detail_json=detail or {},
        occurred_at=datetime.utcnow(),
    ))


def _assert_record_scope(db, record, user, *, write=False):
    from app.modules.internship.services.internship_service import (
        _current_scope,
        _rec_in_scope,
    )
    student = db.get(StudentProfile, record.student_id) if record else None
    if not record or not student or not _rec_in_scope(_current_scope(user), db, record, student):
        raise no_permission("该实习学生不在你的数据范围内")
    if write and record.status == "ARCHIVED":
        raise AppException("DATA_CONFLICT", "已归档实习记录不可调整实习方案")
    return student


def _assert_plan_scope(db, plan: InternshipBatchPlan, user, action: str) -> InternshipBatch:
    from app.modules.internship.services.internship_plan_service import _assert_plan_batch_scope

    batch = db.get(InternshipBatch, int(plan.batch_id))
    if not batch or batch.is_deleted or batch.tenant_id != _tid():
        raise not_found("实习方案所属批次不存在")
    _assert_plan_batch_scope(db, batch, user, action)
    return batch


def _ensure_ack(db, *, plan, record) -> InternshipPlanAck:
    ack = db.scalar(select(InternshipPlanAck).where(
        InternshipPlanAck.tenant_id == _tid(),
        InternshipPlanAck.plan_id == plan.id,
        InternshipPlanAck.internship_id == record.id,
    ).with_for_update())
    if ack:
        if ack.is_deleted:
            ack.is_deleted = False
            ack.status = "PENDING"
            ack.acknowledged_at = None
            ack.version = int(ack.version or 0) + 1
        return ack
    ack = InternshipPlanAck(
        tenant_id=_tid(),
        plan_id=plan.id,
        internship_id=record.id,
        student_id=record.student_id,
        status="PENDING",
    )
    db.add(ack)
    db.flush()
    return ack


def ensure_assignment_in_tx(
    db, *, plan: InternshipBatchPlan, record: InternshipRecord, user=None,
    source: str = "MANUAL", primary: bool = False,
) -> InternshipPlanAssignment:
    if plan.status != "PUBLISHED" or plan.is_deleted:
        raise AppException("DATA_CONFLICT", "仅已发布实习方案可以分配给学生")
    existing = db.scalar(select(InternshipPlanAssignment).where(
        InternshipPlanAssignment.tenant_id == _tid(),
        InternshipPlanAssignment.internship_id == record.id,
        InternshipPlanAssignment.plan_id == plan.id,
    ).with_for_update())
    now = datetime.utcnow()
    if existing:
        if existing.status == "ACTIVE" and not existing.is_deleted:
            if primary and not existing.is_primary:
                existing.is_primary = True
                existing.assignment_source = source
                existing.version = int(existing.version or 0) + 1
            _ensure_ack(db, plan=plan, record=record)
            init_progress_for_plan(db, plan, [record])
            return existing
        existing.is_deleted = False
        existing.status = "ACTIVE"
        existing.is_primary = bool(primary)
        existing.assignment_source = source
        existing.assigned_by_name = _operator(user)
        existing.assigned_at = now
        existing.removed_at = None
        existing.remove_reason = None
        existing.version = int(existing.version or 0) + 1
        assignment = existing
    else:
        assignment = InternshipPlanAssignment(
            tenant_id=_tid(),
            internship_id=record.id,
            student_id=record.student_id,
            plan_id=plan.id,
            plan_batch_id=plan.batch_id,
            assignment_source=source,
            is_primary=bool(primary),
            status="ACTIVE",
            assigned_by_name=_operator(user),
            assigned_at=now,
        )
        db.add(assignment)
        db.flush()
    _ensure_ack(db, plan=plan, record=record)
    init_progress_for_plan(db, plan, [record])
    _audit(db, assignment.id, "ASSIGN", {
        "internshipId": str(record.id),
        "studentId": str(record.student_id),
        "planId": str(plan.id),
        "planBatchId": str(plan.batch_id),
        "primary": bool(primary),
        "source": source,
    }, user=user)
    return assignment


def ensure_primary_assignment_in_tx(db, *, plan, record, user=None):
    return ensure_assignment_in_tx(
        db, plan=plan, record=record, user=user,
        source="PRIMARY_AUTO", primary=True,
    )


def _view(db, assignment: InternshipPlanAssignment) -> dict:
    plan = db.get(InternshipBatchPlan, assignment.plan_id)
    batch = db.get(InternshipBatch, assignment.plan_batch_id)
    ack = db.scalar(select(InternshipPlanAck).where(
        InternshipPlanAck.tenant_id == _tid(),
        InternshipPlanAck.plan_id == assignment.plan_id,
        InternshipPlanAck.internship_id == assignment.internship_id,
        InternshipPlanAck.is_deleted.is_(False),
    ))
    progress = db.scalars(select(InternshipPlanTaskProgress).where(
        InternshipPlanTaskProgress.tenant_id == _tid(),
        InternshipPlanTaskProgress.plan_id == assignment.plan_id,
        InternshipPlanTaskProgress.internship_id == assignment.internship_id,
        InternshipPlanTaskProgress.is_deleted.is_(False),
    )).all()
    approved = sum(1 for row in progress if row.status == "APPROVED")
    started = sum(1 for row in progress if row.status != "NOT_STARTED")
    return {
        "id": str(assignment.id),
        "internshipId": str(assignment.internship_id),
        "studentId": str(assignment.student_id),
        "planId": str(assignment.plan_id),
        "planBatchId": str(assignment.plan_batch_id),
        "planTitle": plan.title if plan else "",
        "planStatus": plan.status if plan else "",
        "batchName": batch.batch_name if batch else "",
        "internshipType": plan.internship_type if plan else "",
        "isPrimary": bool(assignment.is_primary),
        "assignmentSource": assignment.assignment_source,
        "status": assignment.status,
        "assignedByName": assignment.assigned_by_name or "",
        "assignedAt": _iso(assignment.assigned_at) or "",
        "ackStatus": ack.status if ack else "PENDING",
        "taskCount": len(progress),
        "startedTaskCount": started,
        "approvedTaskCount": approved,
        "version": int(assignment.version or 0),
    }


def list_assignments(record_id, user=None) -> dict:
    with session() as db:
        record = db.get(InternshipRecord, _as_id(record_id))
        if not record or record.is_deleted or record.tenant_id != _tid():
            raise not_found("实习学生记录不存在")
        _assert_record_scope(db, record, user)
        rows = db.scalars(select(InternshipPlanAssignment).where(
            InternshipPlanAssignment.tenant_id == _tid(),
            InternshipPlanAssignment.internship_id == record.id,
            InternshipPlanAssignment.status == "ACTIVE",
            InternshipPlanAssignment.is_deleted.is_(False),
        ).order_by(
            InternshipPlanAssignment.is_primary.desc(),
            InternshipPlanAssignment.assigned_at.asc(),
            InternshipPlanAssignment.id.asc(),
        )).all()
        return {
            "internshipId": str(record.id),
            "items": [_view(db, row) for row in rows],
            "total": len(rows),
        }


def plan_options(record_id, user=None, keyword: str = "") -> list[dict]:
    with session() as db:
        record = db.get(InternshipRecord, _as_id(record_id))
        if not record or record.is_deleted or record.tenant_id != _tid():
            raise not_found("实习学生记录不存在")
        _assert_record_scope(db, record, user)
        plans = db.scalars(select(InternshipBatchPlan).where(
            InternshipBatchPlan.tenant_id == _tid(),
            InternshipBatchPlan.status == "PUBLISHED",
            InternshipBatchPlan.is_deleted.is_(False),
        ).order_by(InternshipBatchPlan.id.desc())).all()
        term = str(keyword or "").strip().lower()
        assigned_ids = set(db.scalars(select(InternshipPlanAssignment.plan_id).where(
            InternshipPlanAssignment.tenant_id == _tid(),
            InternshipPlanAssignment.internship_id == record.id,
            InternshipPlanAssignment.status == "ACTIVE",
            InternshipPlanAssignment.is_deleted.is_(False),
        )).all())
        out = []
        for plan in plans:
            try:
                batch = _assert_plan_scope(db, plan, user, "选择实习方案")
            except AppException as exc:
                if exc.code in {"NO_PERMISSION", "NO_DATA_SCOPE"}:
                    continue
                raise
            if batch.status != "RUNNING":
                continue
            label = f"{batch.batch_name} · {plan.title}"
            if term and term not in label.lower():
                continue
            out.append({
                "id": str(plan.id),
                "label": label,
                "title": plan.title,
                "batchId": str(plan.batch_id),
                "batchName": batch.batch_name,
                "internshipType": plan.internship_type or "",
                "alreadyAssigned": int(plan.id) in {int(x) for x in assigned_ids},
            })
        return out[:200]


def assign_plans(record_id, plan_ids, user=None, source: str = "MANUAL") -> dict:
    ids = []
    for raw in plan_ids or []:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "实习方案 ID 格式非法") from None
        if pid > 0 and pid not in ids:
            ids.append(pid)
    if not ids:
        raise AppException("VALIDATION_ERROR", "请至少选择一个实习方案")
    if len(ids) > 20:
        raise AppException("VALIDATION_ERROR", "单次最多分配 20 个实习方案")

    with session() as db:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == _as_id(record_id),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
        ).with_for_update())
        if not record:
            raise not_found("实习学生记录不存在")
        _assert_record_scope(db, record, user, write=True)

        added = 0
        already = 0
        assignments = []
        for plan_id in ids:
            plan = db.scalar(select(InternshipBatchPlan).where(
                InternshipBatchPlan.id == plan_id,
                InternshipBatchPlan.tenant_id == _tid(),
                InternshipBatchPlan.status == "PUBLISHED",
                InternshipBatchPlan.is_deleted.is_(False),
            ).with_for_update())
            if not plan:
                raise AppException("DATA_CONFLICT", f"实习方案 {plan_id} 不存在或未发布")
            plan_batch = _assert_plan_scope(db, plan, user, "分配实习方案")
            if plan_batch.status != "RUNNING":
                raise AppException(
                    "DATA_CONFLICT",
                    f"实习方案 {plan_id} 所属批次不是进行中状态，不能新增分配",
                )
            existing = db.scalar(select(InternshipPlanAssignment).where(
                InternshipPlanAssignment.tenant_id == _tid(),
                InternshipPlanAssignment.internship_id == record.id,
                InternshipPlanAssignment.plan_id == plan.id,
            ).with_for_update())
            was_active = bool(existing and existing.status == "ACTIVE" and not existing.is_deleted)
            assignment = ensure_assignment_in_tx(
                db, plan=plan, record=record, user=user, source=source, primary=False)
            if was_active:
                already += 1
            else:
                added += 1
            assignments.append(assignment)

        db.commit()
        return {
            "added": added,
            "alreadyAssigned": already,
            "items": [_view(db, row) for row in assignments],
        }


def remove_assignment(record_id, assignment_id, *, reason: str, expected_version, user=None) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "移除方案原因不少于 2 个字")
    try:
        expected = int(expected_version)
    except (TypeError, ValueError):
        raise AppException("DATA_CONFLICT", "缺少有效方案分配版本，请刷新后重试") from None

    with session() as db:
        record = db.get(InternshipRecord, _as_id(record_id))
        if not record or record.is_deleted or record.tenant_id != _tid():
            raise not_found("实习学生记录不存在")
        _assert_record_scope(db, record, user, write=True)
        row = db.scalar(select(InternshipPlanAssignment).where(
            InternshipPlanAssignment.id == _as_id(assignment_id),
            InternshipPlanAssignment.tenant_id == _tid(),
            InternshipPlanAssignment.internship_id == record.id,
            InternshipPlanAssignment.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("方案分配关系不存在")
        if int(row.version or 0) != expected:
            raise AppException("DATA_CONFLICT", "方案分配已被其他用户修改，请刷新后重试")
        if row.is_primary:
            raise AppException("DATA_CONFLICT", "主批次实习方案不能从学生记录中移除")
        if row.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "该方案已不在学生当前分配中")

        ack = db.scalar(select(InternshipPlanAck).where(
            InternshipPlanAck.tenant_id == _tid(),
            InternshipPlanAck.plan_id == row.plan_id,
            InternshipPlanAck.internship_id == row.internship_id,
            InternshipPlanAck.is_deleted.is_(False),
        ))
        if ack and ack.status == "ACKNOWLEDGED":
            raise AppException("DATA_CONFLICT", "学生已经确认该方案，不能直接移除")
        started = db.scalar(select(InternshipPlanTaskProgress.id).where(
            InternshipPlanTaskProgress.tenant_id == _tid(),
            InternshipPlanTaskProgress.plan_id == row.plan_id,
            InternshipPlanTaskProgress.internship_id == row.internship_id,
            InternshipPlanTaskProgress.status != "NOT_STARTED",
            InternshipPlanTaskProgress.is_deleted.is_(False),
        ).limit(1))
        if started:
            raise AppException("DATA_CONFLICT", "该方案已有任务办理记录，不能直接移除")

        row.status = "REMOVED"
        row.removed_at = datetime.utcnow()
        row.remove_reason = reason
        row.version = int(row.version or 0) + 1
        _audit(db, row.id, "REMOVE", {
            "internshipId": str(record.id),
            "planId": str(row.plan_id),
            "reason": reason,
        }, user=user)
        db.commit()
        return {"id": str(row.id), "status": row.status, "version": int(row.version or 0)}
