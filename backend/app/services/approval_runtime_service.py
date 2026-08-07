"""A1 审批中心真实运行服务：正式路由 fail-closed，RETURN/REJECT/TRANSFER 语义独立。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.request_context import get_trace_id
from app.db.session import db_enabled
from app.services import approval_service as base
from app.services.message_identity import resolve_message_user_id


def _require_db() -> None:
    if not db_enabled():
        raise AppException(
            "APPROVAL_BACKEND_UNAVAILABLE",
            "审批中心需要真实数据库，当前不可展示演示数据或产生假成功",
            http_status=503,
        )


def _user(user=None) -> dict:
    return user or get_current_user_ctx() or {}


def _tid() -> int:
    try:
        value = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        value = 0
    if not value:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文", http_status=400)
    return value


def _allowed(status: str) -> list[str]:
    return ["APPROVE", "RETURN", "REJECT", "TRANSFER"] if str(status).upper() == "PENDING" else []


def _contract(result: dict, next_todo=None) -> dict:
    out = dict(result or {})
    out["allowedActions"] = _allowed(out.get("status"))
    out["auditId"] = get_trace_id()
    out["nextTodo"] = next_todo
    return out


def _task_can_act(db, task, inst, user=None) -> bool:
    """与既有 SYS-14 节点动作策略保持同一事实源。"""
    from app.services import db_service

    if db_service._can_manage_all_approvals(
        user,
        workflow_code=(inst.workflow_code if inst else None),
        node_code=task.node_code,
    ):
        return True
    uid = db_service._approval_actor_id(user)
    return bool(uid and int(task.assignee_id) == int(uid))


def _enrich_rows(rows: list[dict], *, user=None) -> list[dict]:
    """列表补齐实例状态、业务对象、期限和 allowedActions；前端不得自己猜动作。"""
    if not rows:
        return rows
    from sqlalchemy import select
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service

    task_ids = []
    for row in rows:
        try:
            task_ids.append(int(row.get("taskId") or 0))
        except (TypeError, ValueError):
            continue
    if not task_ids:
        return rows
    with db_service.session() as db:
        tasks = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.id.in_(task_ids),
            WorkflowTask.is_deleted.is_(False),
        )).all()
        task_map = {int(x.id): x for x in tasks}
        instance_ids = {x.instance_id for x in tasks}
        instances = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.id.in_(instance_ids),
            WorkflowInstance.is_deleted.is_(False),
        )).all() if instance_ids else []
        inst_map = {int(x.id): x for x in instances}
        now = datetime.utcnow()
        for row in rows:
            try:
                task = task_map.get(int(row.get("taskId") or 0))
            except (TypeError, ValueError):
                task = None
            if not task:
                row["allowedActions"] = []
                continue
            inst = inst_map.get(int(task.instance_id))
            row["instanceStatus"] = inst.status if inst else ""
            row["currentInstanceNode"] = inst.current_node if inst else ""
            row["sourceBizId"] = str(inst.source_biz_id) if inst else ""
            row["deadlineAt"] = task.deadline_at.isoformat(timespec="seconds") if task.deadline_at else None
            row["urgency"] = (
                "OVERDUE" if task.deadline_at and task.deadline_at < now
                else "NEAR_DEADLINE" if task.deadline_at and task.deadline_at <= now + timedelta(hours=24)
                else "NORMAL"
            )
            row["allowedActions"] = _allowed(task.status) if _task_can_act(db, task, inst, user) else []
    return rows


def list_tasks(page, page_size, *, user=None, keyword=None, biz_type=None):
    _require_db()
    rows, total = base.list_tasks(page, page_size, user=user, keyword=keyword, biz_type=biz_type)
    return _enrich_rows(rows, user=user), total


def list_processed(page, page_size, *, user=None, keyword=None, biz_type=None, result=None):
    _require_db()
    rows, total = base.list_processed(
        page, page_size, user=user, keyword=keyword, biz_type=biz_type, result=result
    )
    return _enrich_rows(rows, user=user), total


def get_task(task_id: str, *, user=None) -> dict:
    _require_db()
    from sqlalchemy import select
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service

    try:
        task_id_int = int(task_id)
    except (TypeError, ValueError):
        raise not_found("审批任务不存在")
    with db_service.session() as db:
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == task_id_int,
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False),
        )).first()
        if not task:
            raise not_found("审批任务不存在")
        # 复用既有审批安全策略：assignee + approval.manage + SYS-14 节点动作策略。
        db_service._assert_task_assignee(db, task, user)
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == task.instance_id,
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False),
        )).first()
        if not inst:
            raise not_found("审批实例不存在")
        row = db_service._task_row(task, inst)
        row["instanceStatus"] = inst.status
        row["currentInstanceNode"] = inst.current_node or ""
        row["sourceBizId"] = str(inst.source_biz_id)
        row["deadlineAt"] = task.deadline_at.isoformat(timespec="seconds") if task.deadline_at else None
        now = datetime.utcnow()
        row["urgency"] = (
            "OVERDUE" if task.deadline_at and task.deadline_at < now
            else "NEAR_DEADLINE" if task.deadline_at and task.deadline_at <= now + timedelta(hours=24)
            else "NORMAL"
        )
        row["allowedActions"] = _allowed(task.status) if _task_can_act(db, task, inst, user) else []
        history = db.scalars(select(WorkflowTask).where(
            WorkflowTask.instance_id == inst.id,
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False),
        ).order_by(WorkflowTask.created_at, WorkflowTask.id)).all()
        row["history"] = [{
            "taskId": str(x.id),
            "nodeCode": x.node_code or "",
            "action": x.status,
            "comment": x.action_reason or "",
            "assigneeId": str(x.assignee_id),
            "createdAt": x.created_at.isoformat(timespec="seconds") if x.created_at else None,
            "actedAt": x.acted_at.isoformat(timespec="seconds") if x.acted_at else None,
        } for x in history]
        row["attachments"] = []
        row["diff"] = []
        return row


def summary(*, user=None) -> dict:
    _require_db()
    from sqlalchemy import func, select
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service

    now = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    cond = [
        WorkflowTask.tenant_id == _tid(),
        WorkflowTask.is_deleted.is_(False),
        WorkflowTask.status == "PENDING",
        WorkflowInstance.tenant_id == _tid(),
        WorkflowInstance.is_deleted.is_(False),
    ]
    if not db_service._can_manage_all_approvals(user):
        cond.append(WorkflowTask.assignee_id == db_service._approval_actor_id(user))
    with db_service.session() as db:
        q = select(WorkflowTask, WorkflowInstance).join(
            WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id
        ).where(*cond)
        rows = db.execute(q.order_by(WorkflowTask.deadline_at, WorkflowTask.id).limit(500)).all()
        total = int(db.scalar(
            select(func.count()).select_from(WorkflowTask).join(
                WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id
            ).where(*cond)
        ) or 0)
        today = sum(1 for t, _ in rows if t.created_at and t.created_at >= start)
        overdue = [(t, i) for t, i in rows if t.deadline_at and t.deadline_at < now]
        near = [(t, i) for t, i in rows if t.deadline_at and now <= t.deadline_at <= now + timedelta(hours=24)]
        by = {}
        for _, inst in rows:
            key = inst.source_biz_type or "GENERAL"
            by[key] = by.get(key, 0) + 1
        overdue_rows = [db_service._task_row(t, i) for t, i in overdue[:10]]
        for item, (task, inst) in zip(overdue_rows, overdue[:10]):
            item["instanceStatus"] = inst.status
            item["sourceBizId"] = str(inst.source_biz_id)
            item["deadlineAt"] = task.deadline_at.isoformat(timespec="seconds") if task.deadline_at else None
            item["urgency"] = "OVERDUE"
            item["allowedActions"] = _allowed(task.status) if _task_can_act(db, task, inst, user) else []
        return {
            "total": total,
            "todayNew": today,
            "overdue": len(overdue),
            "nearDeadline": len(near),
            "byBizType": [{"bizType": k, "count": v} for k, v in sorted(by.items())],
            "overdueList": overdue_rows,
            "asOf": datetime.now().isoformat(timespec="seconds"),
        }


def approve(task_id, comment, *, user=None, version=None):
    _require_db()
    get_task(task_id, user=user)
    return _contract(base.approve(task_id, comment, user=user, version=version))


def reject(task_id, reason, *, user=None, version=None):
    _require_db()
    get_task(task_id, user=user)
    return _contract(base.reject(task_id, reason, user=user, version=version))


def return_for_revision(task_id, reason, *, user=None, version=None):
    """退回不是驳回：实例继续 RUNNING，并真实生成申请人重提待办 + 站内消息。"""
    _require_db()
    base._check_return_reason(reason)
    from sqlalchemy import select
    from app.core.optimistic_lock import atomic_versioned_update, require_expected_version
    from app.models import UnifiedMessage, UnifiedTodo, WorkflowInstance, WorkflowTask
    from app.services import db_service
    from app.services import mock_audit_service as audit

    require_expected_version(version)
    with db_service.session() as db:
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == int(task_id),
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False),
        ).with_for_update()).first()
        if not task:
            raise not_found("审批任务不存在")
        db_service._assert_task_assignee(db, task, user)
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == task.instance_id,
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False),
        ).with_for_update()).first()
        if not inst:
            raise not_found("审批实例不存在")

        atomic_versioned_update(
            db, WorkflowTask, entity_id=int(task_id), tenant_id=_tid(),
            expected_version=version, expected_status="PENDING",
            values={
                "status": "RETURNED",
                "acted_at": datetime.utcnow(),
                "action_reason": reason.strip(),
            },
        )
        inst.status = "RUNNING"
        inst.current_node = "APPLICANT_RESUBMIT"
        inst.version = int(inst.version or 0) + 1

        # 去重键不包含 is_deleted：必须连软删记录一起查，存在则原位恢复，禁止插入碰唯一键。
        todo = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == inst.source_module,
            UnifiedTodo.source_biz_id == inst.source_biz_id,
            UnifiedTodo.todo_type == "APPROVAL_RESUBMIT",
            UnifiedTodo.assignee_id == inst.applicant_id,
        ).with_for_update()).first()
        if not todo:
            todo = UnifiedTodo(
                tenant_id=_tid(),
                source_module=inst.source_module,
                source_biz_type=inst.source_biz_type,
                source_biz_id=inst.source_biz_id,
                todo_type="APPROVAL_RESUBMIT",
                assignee_id=inst.applicant_id,
                title=f"{inst.title or '审批申请'}：修改并重新提交",
                status="PENDING",
                remark=reason.strip(),
            )
            db.add(todo)
        else:
            todo.is_deleted = False
            todo.status = "PENDING"
            todo.title = f"{inst.title or '审批申请'}：修改并重新提交"
            todo.remark = reason.strip()
            todo.version = int(todo.version or 0) + 1
        db.flush()

        db.add(UnifiedMessage(
            tenant_id=_tid(),
            receiver_id=inst.applicant_id,
            receiver_user_id=inst.applicant_id,
            receiver_type="STUDENT",
            receiver_context_key="GLOBAL",
            source_module=inst.source_module,
            source_biz_id=inst.source_biz_id,
            title=f"{inst.title or '审批申请'}已退回修改",
            content=reason.strip(),
            message_type="TODO_NOTICE",
            category="TODO",
            status="UNREAD",
            delivery_status="DELIVERED",
            delivered_at=datetime.utcnow(),
            action_key="APPROVAL_RESUBMIT",
            action_params_json={
                "instanceId": str(inst.id),
                "sourceModule": inst.source_module,
                "sourceBizType": inst.source_biz_type,
                "sourceBizId": str(inst.source_biz_id),
            },
            remark="RETURNED",
        ))
        audit.record_critical(
            "审批退回修改",
            method="POST",
            path=f"/api/v1/approvals/tasks/{task_id}/return",
            status_code=200,
            target_type="approval",
            target_id=str(task_id),
            detail={
                "action": "RETURNED",
                "instanceId": str(inst.id),
                "todoId": str(todo.id),
                "reason": reason.strip(),
            },
            db=db,
        )
        db.commit()
        return _contract({
            "taskId": str(task_id),
            "status": "RETURNED",
            "instanceStatus": "RUNNING",
            "version": int(version) + 1,
        }, {
            "todoId": str(todo.id),
            "status": "PENDING",
            "action": "RESUBMIT",
            "sourceBizId": str(inst.source_biz_id),
        })


def resubmit(instance_id, *, user=None, version=None, comment=None):
    """申请人重提：回到最近一次 RETURNED 的原审批节点。"""
    _require_db()
    from sqlalchemy import select
    from app.core.optimistic_lock import require_expected_version
    from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask
    from app.services import db_service
    from app.services import mock_audit_service as audit

    require_expected_version(version)
    actor_id = resolve_message_user_id(_user(user))
    with db_service.session() as db:
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == int(instance_id),
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False),
        ).with_for_update()).first()
        if not inst:
            raise not_found("审批实例不存在")
        if int(inst.applicant_id) != int(actor_id or 0):
            raise no_permission("仅申请人本人可重新提交")
        if inst.status != "RUNNING" or inst.current_node != "APPLICANT_RESUBMIT":
            raise AppException("APPROVAL_STATE_CONFLICT", "当前申请不处于待修改重提状态", http_status=409)
        if int(inst.version or 0) != int(version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "申请已发生变化，请刷新后重试", http_status=409)
        old = db.scalars(select(WorkflowTask).where(
            WorkflowTask.instance_id == inst.id,
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False),
            WorkflowTask.status == "RETURNED",
        ).order_by(WorkflowTask.acted_at.desc(), WorkflowTask.id.desc()).limit(1)).first()
        if not old:
            raise AppException("APPROVAL_STATE_CONFLICT", "未找到可恢复的退回节点", http_status=409)
        new_task = WorkflowTask(
            tenant_id=_tid(),
            instance_id=inst.id,
            node_code=old.node_code,
            assignee_id=old.assignee_id,
            status="PENDING",
            deadline_at=old.deadline_at,
            remark=old.remark,
        )
        db.add(new_task)
        inst.current_node = old.node_code
        inst.version = int(inst.version or 0) + 1
        todo = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == inst.source_module,
            UnifiedTodo.source_biz_id == inst.source_biz_id,
            UnifiedTodo.todo_type == "APPROVAL_RESUBMIT",
            UnifiedTodo.assignee_id == inst.applicant_id,
            UnifiedTodo.is_deleted.is_(False),
        ).with_for_update()).first()
        if todo:
            todo.status = "DONE"
            todo.version = int(todo.version or 0) + 1
        db.flush()
        audit.record_critical(
            "审批重新提交",
            method="POST",
            path=f"/api/v1/approvals/instances/{instance_id}/resubmit",
            status_code=200,
            target_type="approval",
            target_id=str(instance_id),
            detail={"action": "RESUBMIT", "newTaskId": str(new_task.id), "comment": comment or ""},
            db=db,
        )
        db.commit()
        return {
            "instanceId": str(inst.id),
            "status": "RESUBMITTED",
            "instanceStatus": "RUNNING",
            "currentNode": inst.current_node,
            "version": inst.version,
            "newTaskId": str(new_task.id),
            "allowedActions": [],
            "auditId": get_trace_id(),
            "nextTodo": None,
        }


def transfer(task_id, target_user_id, comment, *, user=None, version=None):
    """转办：原任务 TRANSFERRED，新任务 PENDING 交目标办理人。"""
    _require_db()
    from sqlalchemy import select
    from app.core.optimistic_lock import atomic_versioned_update, require_expected_version
    from app.models import User, WorkflowInstance, WorkflowTask
    from app.services import db_service
    from app.services import mock_audit_service as audit

    require_expected_version(version)
    try:
        target_id = int(target_user_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "转办目标无效")
    with db_service.session() as db:
        target = db.scalars(select(User).where(
            User.id == target_id,
            User.tenant_id == _tid(),
            User.is_deleted.is_(False),
            User.status == "ACTIVE",
        )).first()
        if not target or str(getattr(target, "user_type", "")).upper() == "STUDENT":
            raise AppException("VALIDATION_ERROR", "转办目标不存在、已停用或不是教职工")
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == int(task_id),
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False),
        ).with_for_update()).first()
        if not task:
            raise not_found("审批任务不存在")
        db_service._assert_task_assignee(db, task, user)
        if int(task.assignee_id) == target_id:
            raise AppException("VALIDATION_ERROR", "不能转办给当前办理人")
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == task.instance_id,
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False),
        )).first()
        if not inst:
            raise not_found("审批实例不存在")
        atomic_versioned_update(
            db, WorkflowTask, entity_id=int(task_id), tenant_id=_tid(),
            expected_version=version, expected_status="PENDING",
            values={
                "status": "TRANSFERRED",
                "acted_at": datetime.utcnow(),
                "action_reason": (comment or "").strip(),
            },
        )
        new_task = WorkflowTask(
            tenant_id=_tid(),
            instance_id=task.instance_id,
            node_code=task.node_code,
            assignee_id=target_id,
            status="PENDING",
            deadline_at=task.deadline_at,
            remark=task.remark,
        )
        db.add(new_task)
        db.flush()
        audit.record_critical(
            "审批转办", method="POST",
            path=f"/api/v1/approvals/tasks/{task_id}/transfer",
            status_code=200, target_type="approval", target_id=str(task_id),
            detail={"action": "TRANSFERRED", "to": str(target_id), "newTaskId": str(new_task.id)},
            db=db,
        )
        db.commit()
        return _contract({
            "taskId": str(task_id),
            "status": "TRANSFERRED",
            "instanceStatus": inst.status,
            "version": int(version) + 1,
            "newTaskId": str(new_task.id),
            "transferredTo": target.real_name or target.login_name or str(target_id),
        })


def transfer_targets(*, user=None, limit=100):
    _require_db()
    from sqlalchemy import func, select
    from app.models import User, WorkflowTask
    from app.services import db_service

    me = resolve_message_user_id(_user(user))
    with db_service.session() as db:
        users = db.scalars(select(User).where(
            User.tenant_id == _tid(),
            User.is_deleted.is_(False),
            User.status == "ACTIVE",
        ).order_by(User.id).limit(min(max(int(limit), 1), 200))).all()
        out = []
        for row in users:
            if int(row.id) == int(me or 0) or str(row.user_type or "").upper() == "STUDENT":
                continue
            pending = int(db.scalar(select(func.count()).select_from(WorkflowTask).where(
                WorkflowTask.tenant_id == _tid(),
                WorkflowTask.is_deleted.is_(False),
                WorkflowTask.status == "PENDING",
                WorkflowTask.assignee_id == row.id,
            )) or 0)
            out.append({
                "userId": str(row.id),
                "userName": row.real_name or row.login_name or str(row.id),
                "roleName": row.user_type or "教职工",
                "orgName": "",
                "pendingCount": pending,
            })
        return out


def batch_process(items, action, *, user=None, reason=None, target_user_id=None, comment=None):
    action = str(action or "").upper()
    if action not in {"APPROVE", "RETURN", "REJECT", "TRANSFER"}:
        raise AppException("VALIDATION_ERROR", "不支持的批量审批动作")
    results = []
    for item in items:
        task_id = str(item.get("taskId") or "")
        version = item.get("version")
        try:
            if action == "APPROVE":
                value = approve(task_id, comment, user=user, version=version)
            elif action == "RETURN":
                value = return_for_revision(task_id, reason or "", user=user, version=version)
            elif action == "REJECT":
                value = reject(task_id, reason or "", user=user, version=version)
            else:
                value = transfer(task_id, target_user_id or "", comment, user=user, version=version)
            results.append({"id": task_id, "result": "SUCCESS", "errorCode": None, "newVersion": value.get("version")})
        except AppException as exc:
            results.append({
                "id": task_id,
                "result": "FAILED",
                "errorCode": getattr(exc, "code", None) or "APPROVAL_FAILED",
                "message": getattr(exc, "message", None) or str(exc),
                "newVersion": None,
            })
    succeeded = sum(1 for x in results if x["result"] == "SUCCESS")
    return {
        "action": action,
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "skipped": 0,
        "results": results,
        "auditId": get_trace_id(),
    }


def list_cc(page, page_size, *, user=None, keyword=None, read_status=None):
    _require_db()
    from sqlalchemy import func, select
    from app.models import UnifiedMessage
    from app.services import db_service

    uid = resolve_message_user_id(_user(user))
    if not uid:
        raise no_permission("未识别到当前用户")
    cond = [
        UnifiedMessage.tenant_id == _tid(),
        UnifiedMessage.is_deleted.is_(False),
        UnifiedMessage.receiver_user_id == uid,
        UnifiedMessage.source_module == "approval",
        UnifiedMessage.action_key == "APPROVAL_CC",
    ]
    if read_status:
        cond.append(UnifiedMessage.status == read_status)
    if keyword:
        cond.append(UnifiedMessage.title.like(f"%{keyword.strip()}%"))
    with db_service.session() as db:
        total = int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(*cond)) or 0)
        rows = db.scalars(select(UnifiedMessage).where(*cond)
                          .order_by(UnifiedMessage.created_at.desc(), UnifiedMessage.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [{
            "id": str(x.id),
            "taskId": str(x.source_biz_id or ""),
            "title": x.title,
            "sourceBizType": "",
            "applicantName": "",
            "className": "",
            "ccReason": x.content or "",
            "ccTime": x.created_at.isoformat(timespec="seconds") if x.created_at else "",
            "readStatus": x.status,
        } for x in rows], total


def list_returned(page, page_size, *, user=None, keyword=None, rectify_status=None):
    rows, total = list_processed(
        page, page_size, user=user, keyword=keyword, result="RETURNED"
    )
    for row in rows:
        inst_status = str(row.get("instanceStatus") or "").upper()
        current_node = str(row.get("currentInstanceNode") or "").upper()
        if inst_status == "RUNNING" and current_node == "APPLICANT_RESUBMIT":
            row["rectifyStatus"] = "PENDING_RESUBMIT"
        elif inst_status == "RUNNING":
            row["rectifyStatus"] = "RESUBMITTED"
        else:
            row["rectifyStatus"] = "CLOSED"
    if rectify_status:
        wanted = str(rectify_status).upper()
        rows = [x for x in rows if x["rectifyStatus"] == wanted]
        # 过滤发生在服务端返回的真实页内；total 不冒充全库命中数。
        total = len(rows)
    return rows, total


def approval_audit(*, user=None, limit=20):
    _require_db()
    from app.services import db_service
    rows, _ = db_service.audit_query(1, 100)
    out = []
    for row in rows:
        if (
            "approval" not in str(row.get("resource") or "").lower()
            and "/approvals/" not in str(row.get("path") or "").lower()
            and "审批" not in str(row.get("action") or "")
        ):
            continue
        out.append({
            "id": row.get("auditId"),
            "who": row.get("actorName") or "系统",
            "roleName": "",
            "time": row.get("occurredAt") or "",
            "action": row.get("action") or "",
            "target": row.get("resource") or "",
            "detail": str(row.get("detail") or ""),
            "requestId": row.get("requestId") or "",
        })
        if len(out) >= limit:
            break
    return out
