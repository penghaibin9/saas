"""A1 审批中心真实运行服务：正式路由 fail-closed，RETURN/REJECT/TRANSFER 语义独立。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.request_context import get_trace_id
from app.db.session import db_enabled
from app.services import approval_service as base
from app.services.message_identity import resolve_message_user_id

# TP-A10：审批业务类型字典的唯一服务端权威。前端此前自己维护一份完整枚举
# （含 COMPANY_CHANGE / MATERIAL_VERIFY 两个全仓 grep 不到任何创建点的臆造类型），
# 新增一种审批就必须记得同步改前端常量，忘改就会出现"能审批但列表筛选不出来"。
#
# 曾经考虑直接复用 WorkflowDefinition.source_biz_type（该表已有 workflow_name 可当
# 标签），但核实后发现那张表的预置 `biz` 字段（如 STATUS_CHANGE）与各业务域实际写在
# WorkflowInstance.source_biz_type 上的真实值（如 AA_STATUS_CHANGE）本身就不一致——
# 这是 runtime_preset_install_service 预置数据自己的既有漂移，不是本项能顺手修的范围，
# 直接借用只会把这个漂移进一步暴露到审批筛选器上。因此改为维护一份与各业务域真实
# `WorkflowInstance(source_biz_type=...)` 写入值逐个核对过的静态字典：
#   LEAVE/AID/FUNDING/DISCIPLINE/DISCIPLINE_REMOVE ← affairs_*_service.py
#   AA_STATUS_CHANGE/AA_GRADE_TASK/AA_GRADE_CHANGE/AA_SCHEDULE_CHANGE ← academic_affairs 模块
#   MESSAGE_CAMPAIGN ← message_campaign_service.py；PROFILE_CORRECTION ← 体验沙箱种子
# 缺一个映射时各处已有 `label || bizType` 兜底显示原始 code，不伪造标签也不阻塞页面。
_BIZ_TYPE_LABELS: dict[str, str] = {
    "LEAVE": "请假审批",
    "AID": "困难认定",
    "FUNDING": "奖助评定",
    "DISCIPLINE": "违纪认定",
    "DISCIPLINE_REMOVE": "违纪解除",
    "AA_STATUS_CHANGE": "学籍异动",
    "AA_GRADE_TASK": "成绩审核",
    "AA_GRADE_CHANGE": "成绩更正",
    "AA_SCHEDULE_CHANGE": "调停课审批",
    "MESSAGE_CAMPAIGN": "消息任务审批",
    "PROFILE_CORRECTION": "信息更正",
    "EMPLOYMENT_DESTINATION": "就业去向登记",
}


def biz_type_options() -> list[dict]:
    return [{"value": k, "label": v} for k, v in _BIZ_TYPE_LABELS.items()]


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


def list_tasks(
    page,
    page_size,
    *,
    user=None,
    keyword=None,
    biz_type=None,
    urgency=None,
    submit_date=None,
):
    _require_db()
    rows, total = base.list_tasks(
        page,
        page_size,
        user=user,
        keyword=keyword,
        biz_type=biz_type,
        urgency=urgency,
        submit_date=submit_date,
    )
    return _enrich_rows(rows, user=user), total


def list_processed(page, page_size, *, user=None, keyword=None, biz_type=None, result=None,
                   acted_from=None, acted_to=None):
    _require_db()
    rows, total = base.list_processed(
        page, page_size, user=user, keyword=keyword, biz_type=biz_type, result=result,
        acted_from=acted_from, acted_to=acted_to,
    )
    return _enrich_rows(rows, user=user), total


def next_task(anchor_task_id, *, user=None, keyword=None, biz_type=None, urgency=None, submit_date=None):
    """TP-A03/A04：真实服务端 seek，取当前筛选队列里锚点任务之后的下一条待办。"""
    _require_db()
    row = base.next_pending_task(
        anchor_task_id, user=user, keyword=keyword, biz_type=biz_type,
        urgency=urgency, submit_date=submit_date,
    )
    if row is None:
        return None
    return _enrich_rows([row], user=user)[0]


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
        from app.services import approval_business_context_service as ctx_svc

        context = ctx_svc.resolve_context(db, inst)
        row["businessContext"] = context
        row["attachments"] = context.get("attachments") or []
        row["diff"] = []
        row["diffNote"] = "各业务域暂未持久化变更前快照，审批详情不展示字段对比"
        return row


def summary(*, user=None) -> dict:
    """待办统计全部由数据库聚合；“今日”统一按租户本地自然日，展示型 overdueList 限 10 行。"""
    _require_db()
    from sqlalchemy import case, func, select
    from app.models import WorkflowInstance, WorkflowTask
    from app.core.timeutil import local_today_bounds_utc
    from app.services import db_service

    now = datetime.utcnow()
    today_start, today_end = local_today_bounds_utc()
    near_until = now + timedelta(hours=24)
    cond = [
        WorkflowTask.tenant_id == _tid(),
        WorkflowTask.is_deleted.is_(False),
        WorkflowTask.status == "PENDING",
        WorkflowInstance.tenant_id == _tid(),
        WorkflowInstance.is_deleted.is_(False),
    ]
    if not db_service._can_manage_all_approvals(user):
        cond.append(WorkflowTask.assignee_id == db_service._approval_actor_id(user))

    join_from = WorkflowTask.__table__.join(
        WorkflowInstance.__table__, WorkflowInstance.id == WorkflowTask.instance_id
    )
    with db_service.session() as db:
        def _count(*extra) -> int:
            return int(db.scalar(
                select(func.count()).select_from(join_from).where(*cond, *extra)
            ) or 0)

        total = _count()
        today = _count(
            WorkflowTask.created_at >= today_start,
            WorkflowTask.created_at < today_end,
        )
        overdue_count = _count(WorkflowTask.deadline_at < now)
        near_count = _count(
            WorkflowTask.deadline_at >= now,
            WorkflowTask.deadline_at <= near_until,
        )
        # TP-W03/P2-04：Workbench「今日已完成」卡片与 todayNew 共用同一个租户本地
        # 日历边界，再换算成 UTC-naive 比较数据库列。凌晨 00:00–08:00（UTC+8）不再
        # 把本地“今天”误切成 UTC 的昨天/今天。
        done_cond = [
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.is_deleted.is_(False),
            WorkflowTask.status.in_(["APPROVED", "REJECTED", "RETURNED", "TRANSFERRED"]),
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False),
            WorkflowTask.acted_at.is_not(None),
            WorkflowTask.acted_at >= today_start,
            WorkflowTask.acted_at < today_end,
        ]
        if not db_service._can_manage_all_approvals(user):
            done_cond.append(WorkflowTask.assignee_id == db_service._approval_actor_id(user))
        done_today = int(db.scalar(
            select(func.count()).select_from(join_from).where(*done_cond)
        ) or 0)
        grouped = db.execute(
            select(
                WorkflowInstance.source_biz_type,
                func.count(),
                func.min(WorkflowTask.created_at),
                func.sum(case((WorkflowTask.deadline_at < now, 1), else_=0)),
            )
            .select_from(join_from)
            .where(*cond)
            .group_by(WorkflowInstance.source_biz_type)
            .order_by(WorkflowInstance.source_biz_type)
        ).all()
        overdue = db.execute(
            select(WorkflowTask, WorkflowInstance)
            .select_from(join_from)
            .where(*cond, WorkflowTask.deadline_at < now)
            .order_by(WorkflowTask.deadline_at, WorkflowTask.id)
            .limit(10)
        ).all()
        overdue_rows = [db_service._task_row(t, i) for t, i in overdue]
        for item, (task, inst) in zip(overdue_rows, overdue):
            item["instanceStatus"] = inst.status
            item["sourceBizId"] = str(inst.source_biz_id)
            item["deadlineAt"] = task.deadline_at.isoformat(timespec="seconds") if task.deadline_at else None
            item["urgency"] = "OVERDUE"
            item["allowedActions"] = _allowed(task.status) if _task_can_act(db, task, inst, user) else []
        return {
            "total": total,
            "todayNew": today,
            "overdue": overdue_count,
            "nearDeadline": near_count,
            "doneToday": done_today,
            "byBizType": [
                {
                    "bizType": biz_type or "GENERAL",
                    "count": int(count or 0),
                    "earliest": earliest.isoformat(timespec="seconds") if earliest else None,
                    "overdue": int(group_overdue or 0),
                }
                for biz_type, count, earliest, group_overdue in grouped
            ],
            "overdueList": overdue_rows,
            "asOf": now.isoformat(timespec="seconds"),
        }


def _assert_context_gate(context: dict, expected_source_version) -> None:
    """TP-A07 compatibility wrapper；真实规则统一在 Context adapter 服务。"""
    from app.services import approval_business_context_service as ctx_svc
    ctx_svc.assert_action_context(context, expected_source_version)


def approve(task_id, comment, *, user=None, version=None, expected_source_version=None):
    """通过：Context/sourceVersion 校验与 task/instance/业务副作用在同一事务。"""
    _require_db()
    from app.services import db_service

    return _contract(db_service.act_task(
        task_id, "APPROVED", comment, user=user, version=version,
        enforce_context_gate=True,
        expected_source_version=expected_source_version,
    ))


def reject(task_id, reason, *, user=None, version=None, expected_source_version=None):
    """驳回终止：与通过共用同事务 sourceVersion 硬门。"""
    _require_db()
    base._check_reject_reason(reason)
    from app.services import db_service

    return _contract(db_service.act_task(
        task_id, "REJECTED", reason, user=user, version=version,
        enforce_context_gate=True,
        expected_source_version=expected_source_version,
    ))


def return_for_revision(task_id, reason, *, user=None, version=None, expected_source_version=None):
    """退回：通用流程进入申请人重提；领域可在同事务内把 RETURN 覆盖为终态。"""
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

        from app.services import approval_business_context_service as ctx_svc
        _assert_context_gate(
            ctx_svc.resolve_context(db, inst, for_update=True),
            expected_source_version,
        )

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
        if (inst.source_biz_type or "") == "EMPLOYMENT_DESTINATION":
            from app.modules.employment.services import employment_destination_submission_service as emp_dest_svc
            emp_dest_svc.apply_return_in_db(db, inst, reason=reason.strip())
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
                "instanceStatus": inst.status,
            },
            db=db,
        )
        db.commit()

        next_todo = None
        if (
            inst.status == "RUNNING"
            and inst.current_node == "APPLICANT_RESUBMIT"
            and not bool(todo.is_deleted)
            and todo.status == "PENDING"
        ):
            next_todo = {
                "todoId": str(todo.id),
                "status": "PENDING",
                "action": "RESUBMIT",
                "sourceBizId": str(inst.source_biz_id),
            }
        return _contract({
            "taskId": str(task_id),
            "status": "RETURNED",
            "instanceStatus": inst.status,
            "currentNode": inst.current_node or "",
            "version": int(version) + 1,
        }, next_todo)


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
        expected_source_version = item.get("expectedSourceVersion")
        try:
            if action == "APPROVE":
                value = approve(
                    task_id, comment, user=user, version=version,
                    expected_source_version=expected_source_version,
                )
            elif action == "RETURN":
                value = return_for_revision(
                    task_id, reason or "", user=user, version=version,
                    expected_source_version=expected_source_version,
                )
            elif action == "REJECT":
                value = reject(
                    task_id, reason or "", user=user, version=version,
                    expected_source_version=expected_source_version,
                )
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
