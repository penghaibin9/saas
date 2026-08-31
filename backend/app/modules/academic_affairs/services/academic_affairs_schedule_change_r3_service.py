"""P1-06/P1-07 hardened schedule-change commands.

All reads and low-risk helpers stay in the legacy service.  Submit/review/cancel are
explicit here so active-origin uniqueness, expectedVersion, exact task-assignee
Authority and the fixed Change -> Task -> Origin lock order are enforceable without
changing conflict, workflow, todo or notification contracts.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.tenant_scoped import tenant_get

from . import academic_affairs_schedule_change_service as _legacy


def __getattr__(name):
    return getattr(_legacy, name)


def _actor_numeric_id(user, *, required=True):
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    if raw.isdigit():
        return int(raw)
    if required:
        raise _legacy.no_data_scope("无法确认当前审批人的真实账号身份")
    return None


def _locked_change(db, cid):
    from app.models import AaScheduleChange

    row = db.query(AaScheduleChange).filter(
        AaScheduleChange.id == int(cid),
        AaScheduleChange.tenant_id == _legacy._tid(),
        AaScheduleChange.is_deleted.is_(False),
    ).with_for_update().first()
    if not row:
        raise not_found("调停课单不存在")
    return row


def submit(body, user) -> dict:
    """Origin lock + active-origin uniqueness before any change/workflow/todo insert."""
    ct = (getattr(body, "changeType", "") or "").upper()
    if ct not in _legacy.CHANGE_TYPES:
        raise AppException("VALIDATION_ERROR", "调停课类型非法（ADJUST/STOP/MAKEUP）")
    reason = (getattr(body, "reason", None) or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调停课原因必填且不少于 5 字")

    with _legacy.session() as db:
        from app.models import AaScheduleBatch, AaScheduleChange, AaScheduleItem

        origin_id = getattr(body, "originItemId", None)
        if not origin_id:
            raise AppException("VALIDATION_ERROR", "originItemId 必填")
        origin = db.query(AaScheduleItem).filter(
            AaScheduleItem.id == int(origin_id),
            AaScheduleItem.tenant_id == _legacy._tid(),
            AaScheduleItem.is_deleted.is_(False),
        ).with_for_update().first()
        if not origin:
            raise not_found("原课表项不存在")
        if origin.status != "EFFECTIVE":
            raise AppException("DATA_CONFLICT", "原课表项已变更/失效，不可再发起调停课", http_status=409)

        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(origin.batch_id),
            AaScheduleBatch.tenant_id == _legacy._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first() if origin.batch_id else None
        _legacy._require_current_published_origin(db, batch, origin)

        existing = db.query(AaScheduleChange).filter(
            AaScheduleChange.tenant_id == _legacy._tid(),
            AaScheduleChange.origin_item_id == int(origin.id),
            AaScheduleChange.status.in_(_legacy._ACTIVE),
            AaScheduleChange.is_deleted.is_(False),
        ).order_by(AaScheduleChange.id).first()
        if existing:
            raise AppException(
                "DATA_CONFLICT",
                "该原课位已有在途调停课单，不能重复发起",
                details={"existingChangeId": str(existing.id)},
                http_status=409,
            )

        ctx = _legacy.build_affairs_context(user, db)
        if not _legacy._can_manage_all(ctx):
            keys = _legacy._derive_keys(user)
            if not origin.teacher_key or origin.teacher_key not in keys:
                raise _legacy.no_data_scope("仅可对本人任课课位发起调停课")
        if ct == "STOP" and not (getattr(body, "makeupPlan", None) or "").strip():
            raise AppException("VALIDATION_ERROR", "停课须填写补课/后续安排说明")

        tw = ts = tsw = tew = tp = tcr = None
        if ct in ("ADJUST", "MAKEUP"):
            if getattr(body, "targetWeekday", None) is None or getattr(body, "targetSlotNo", None) is None:
                raise AppException("VALIDATION_ERROR", "调课/补课须填写目标星期与节次")
            tw, ts = int(body.targetWeekday), int(body.targetSlotNo)
            tsw = int(getattr(body, "targetStartWeek", None) or origin.start_week)
            tew = int(getattr(body, "targetEndWeek", None) or origin.end_week)
            tp = getattr(body, "targetWeekParity", None) or origin.week_parity or "ALL"
            tcr = getattr(body, "targetClassroom", None) or origin.classroom_text
            if ct == "ADJUST":
                _legacy._validate_adjust_window(origin, tsw, tew, tp)
            if tw < 1 or tw > 7:
                raise AppException("VALIDATION_ERROR", "目标星期非法")
            conflict = _legacy._detect_conflict(
                db, origin.batch_id, tw, ts, tsw, tew, tp,
                origin.teacher_key, origin.class_id, tcr, exclude_id=origin.id,
            )
            if conflict:
                raise AppException(
                    "DATA_CONFLICT",
                    f"目标课位冲突（{conflict['type']}）：{conflict['detail']}，单据不予受理",
                    http_status=409,
                )

        uid_num = _actor_numeric_id(user, required=False)
        change = AaScheduleChange(
            tenant_id=_legacy._tid(), term_id=batch.term_id, batch_id=origin.batch_id,
            origin_item_id=origin.id, task_id=origin.task_id, change_type=ct,
            course_name=origin.course_name, class_id=origin.class_id, class_name=origin.class_name,
            teacher_key=origin.teacher_key, teacher_name=origin.teacher_name,
            origin_weekday=origin.weekday, origin_slot_no=origin.slot_no,
            origin_start_week=origin.start_week, origin_end_week=origin.end_week,
            origin_week_parity=origin.week_parity, origin_classroom=origin.classroom_text,
            target_weekday=tw, target_slot_no=ts, target_start_week=tsw, target_end_week=tew,
            target_week_parity=tp, target_classroom=tcr,
            makeup_plan=(getattr(body, "makeupPlan", None) or None), reason=reason,
            applicant_id=uid_num, status="SUBMITTED", current_node="COLLEGE_REVIEW",
        )
        db.add(change)
        db.flush()
        inst = _legacy._open_wf(
            db, change.id, uid_num or 0,
            f"{origin.teacher_name or ''} {_legacy.L_CT[ct]}：{origin.course_name or ''}",
            "COLLEGE_REVIEW", change=change,
        )
        change.workflow_instance_id = inst.id
        _legacy._todo_upsert(
            db, change.id, "COLLEGE_REVIEW",
            f"{_legacy.L_CT[ct]}待学院审：{origin.course_name or ''}", change=change,
        )
        _legacy._audit(db, change.id, "SUBMIT", f"{ct} item={origin.id}")
        db.commit()
        db.refresh(change)
        return _legacy._row(change)


def _pending_task(db, change, instance_id):
    from app.models import WorkflowTask

    tasks = db.query(WorkflowTask).filter(
        WorkflowTask.tenant_id == _legacy._tid(),
        WorkflowTask.instance_id == int(instance_id),
        WorkflowTask.node_code == change.current_node,
        WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False),
    ).order_by(WorkflowTask.id).with_for_update().limit(2).all()
    if len(tasks) != 1:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "当前审批节点没有唯一待办任务，请刷新后重试",
            details={"pendingTaskCount": len(tasks)},
            http_status=409,
        )
    return tasks[0]


def review(cid, user, action, comment="", *, expected_version=None) -> dict:
    """One request handles one node; stale version/non-assignee fail before any side effect."""
    try:
        expected = int(expected_version)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必填且须为非负整数")
    if expected < 0:
        raise AppException("VALIDATION_ERROR", "expectedVersion 必填且须为非负整数")

    action = (action or "").upper()
    with _legacy.session() as db:
        from app.models import AaScheduleItem, WorkflowInstance, WorkflowTask

        change = _locked_change(db, cid)  # lock 1: Change
        if int(change.version or 0) != expected:
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "调停课单版本已变化，请刷新后重试",
                details={"expectedVersion": expected, "currentVersion": int(change.version or 0)},
                http_status=409,
            )
        if change.status not in _legacy._ACTIVE:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该调停课单当前状态不可审批", http_status=409)
        if not change.workflow_instance_id:
            raise AppException("APPROVAL_VERSION_CONFLICT", "调停课单缺少审批流程实例", http_status=409)

        inst = db.get(WorkflowInstance, int(change.workflow_instance_id))
        if not inst or inst.is_deleted or inst.tenant_id != _legacy._tid():
            raise AppException("APPROVAL_VERSION_CONFLICT", "审批流程实例不存在", http_status=409)
        task = _pending_task(db, change, inst.id)  # lock 2: current Task
        actor_id = _actor_numeric_id(user)
        if int(task.assignee_id or 0) != actor_id:
            raise _legacy.no_data_scope("当前账号不是该审批节点的真实受理人")

        if action == "REJECT":
            clean_comment = (comment or "").strip()
            if len(clean_comment) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
            task.status, task.action_reason, task.acted_at = "REJECTED", clean_comment, datetime.utcnow()
            change.status, change.version = "REJECTED", int(change.version or 0) + 1
            inst.status = "REJECTED"
            _legacy._todo_done(db, change.id)
            _legacy._msg(
                db, change.applicant_id or 0, f"{_legacy.L_CT[change.change_type]}未通过",
                clean_comment, "WORKFLOW_RESULT", change.id,
            )
            _legacy._audit(db, change.id, "REJECT", clean_comment)
            db.commit()
            from app.services.message_event_outbox_service import try_process_pending_outbox
            try_process_pending_outbox(worker_id="aa-sched-change-inline")
            db.refresh(change)
            return _legacy._row(change)

        if action != "APPROVE":
            raise AppException("VALIDATION_ERROR", "无效操作")

        task.status, task.acted_at = "APPROVED", datetime.utcnow()
        index = _legacy.NODES.index(change.current_node) if change.current_node in _legacy.NODES else 0
        if index + 1 < len(_legacy.NODES):
            nxt = _legacy.NODES[index + 1]
            change.current_node = nxt
            change.status = _legacy._NODE_STATUS[nxt]
            change.version = int(change.version or 0) + 1
            inst.current_node = nxt
            db.add(WorkflowTask(
                tenant_id=_legacy._tid(), instance_id=inst.id, node_code=nxt,
                assignee_id=_legacy._schedule_change_assignee(db, nxt, change), status="PENDING",
            ))
            _legacy._todo_upsert(
                db, change.id, nxt,
                f"{_legacy.L_CT[change.change_type]}待教务处审：{change.course_name or ''}", change=change,
            )
            _legacy._audit(db, change.id, "STEP", f"->{nxt}")
            db.commit()
            db.refresh(change)
            return _legacy._row(change)

        # lock 3: Origin, only after Change + current Task.
        origin = db.query(AaScheduleItem).filter(
            AaScheduleItem.id == int(change.origin_item_id),
            AaScheduleItem.tenant_id == _legacy._tid(),
            AaScheduleItem.is_deleted.is_(False),
        ).with_for_update().first() if change.origin_item_id else None
        if not origin:
            raise AppException("DATA_CONFLICT", "原课表项不存在，终审不能生效", http_status=409)
        from app.models import AaScheduleBatch
        batch = tenant_get(
            db, AaScheduleBatch, int(origin.batch_id), tenant_id=_legacy._tid()
        ) if origin.batch_id else None
        _legacy._require_current_published_origin(db, batch, origin)
        if change.change_type in ("ADJUST", "STOP") and origin.status != "EFFECTIVE":
            raise AppException("DATA_CONFLICT", "原课表项已被其它操作变更，终审已回滚", http_status=409)

        change.status = "APPROVED"
        change.version = int(change.version or 0) + 1
        inst.status = "APPROVED"
        _legacy._audit(db, change.id, "APPROVE", "终审通过")
        applied = _legacy._apply_schedule(db, change)
        _legacy._todo_done(db, change.id)
        db.commit()
        from app.services.message_event_outbox_service import try_process_pending_outbox
        try_process_pending_outbox(worker_id="aa-sched-change-inline")
        db.refresh(change)
        out = _legacy._row(change)
        out["applied"] = applied
        return out


def cancel(cid, user, reason="") -> dict:
    """Change is always the first lock, so cancel and review cannot overwrite each other."""
    with _legacy.session() as db:
        from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask

        change = _locked_change(db, cid)  # lock 1: Change
        if change.status in ("APPROVED", "APPLIED"):
            raise AppException("DATA_CONFLICT", "已终审通过/已生效，不可撤销", http_status=409)
        if change.status not in _legacy._CANCELLABLE:
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可撤销", http_status=409)

        ctx = _legacy.build_affairs_context(user, db)
        if not _legacy._can_manage_all(ctx):
            keys = _legacy._derive_keys(user)
            if not change.teacher_key or change.teacher_key not in keys:
                raise _legacy.no_data_scope("仅可撤销本人发起的调停课单")

        tasks = []
        inst = None
        if change.workflow_instance_id:
            tasks = db.query(WorkflowTask).filter(
                WorkflowTask.tenant_id == _legacy._tid(),
                WorkflowTask.instance_id == int(change.workflow_instance_id),
                WorkflowTask.status == "PENDING",
                WorkflowTask.is_deleted.is_(False),
            ).order_by(WorkflowTask.id).with_for_update().all()  # lock 2: Task(s)
            inst = db.query(WorkflowInstance).filter(
                WorkflowInstance.id == int(change.workflow_instance_id),
                WorkflowInstance.tenant_id == _legacy._tid(),
                WorkflowInstance.is_deleted.is_(False),
            ).with_for_update().first()
        todos = db.query(UnifiedTodo).filter(
            UnifiedTodo.tenant_id == _legacy._tid(),
            UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_id == int(change.id),
            UnifiedTodo.todo_type == "AA_SCHEDULE_CHANGE_APPROVAL",
            UnifiedTodo.is_deleted.is_(False),
        ).order_by(UnifiedTodo.id).with_for_update().all()

        for task in tasks:
            task.status, task.acted_at = "CANCELLED", datetime.utcnow()
        for todo in todos:
            todo.status, todo.version = "DONE", int(todo.version or 0) + 1
        change.status, change.version = "CANCELLED", int(change.version or 0) + 1
        if inst:
            inst.status = "CANCELLED"
        _legacy._audit(db, change.id, "CANCEL", (reason or "").strip())
        db.commit()
        db.refresh(change)
        return _legacy._row(change)
