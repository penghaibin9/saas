"""审批任务服务：真实审批语义、租户隔离、办理人校验与服务端筛选统一收口。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.pagination import page_slice
from app.core.permissions import has_permission
from app.db.session import db_enabled
from app.services.message_identity import resolve_message_user_id

_now = lambda: datetime.now().isoformat(timespec="seconds")  # noqa: E731

_TASKS: list[dict] = [
    {"taskId": "at-1001", "instanceId": "wi-2001", "tenantId": "1000000000000000001",
     "assigneeId": 0, "title": "张一鸣 · 学籍信息变更", "sourceModule": "student",
     "sourceBizType": "PROFILE_CORRECTION", "applicantName": "张一鸣",
     "nodeCode": "COUNSELOR_REVIEW", "nodeName": "辅导员审核",
     "status": "PENDING", "submittedAt": "2026-07-01 09:32", "stayHours": 26,
     "urgency": "NEAR_DEADLINE", "version": 0},
    {"taskId": "at-1003", "instanceId": "wi-2003", "tenantId": "1000000000000000001",
     "assigneeId": 0, "title": "李二 · 请假延期", "sourceModule": "student",
     "sourceBizType": "LEAVE", "applicantName": "李二",
     "nodeCode": "COUNSELOR_REVIEW", "nodeName": "辅导员审核",
     "status": "PENDING", "submittedAt": "2026-07-02 10:00", "stayHours": 12,
     "urgency": "NORMAL", "version": 0},
]
_PROCESSED: list[dict] = []
_CC: list[dict] = [
    {"taskId": "cc-1", "title": "王晨 · 学业预警处理进展", "status": "CC", "createdAt": "2026-07-02 15:20"},
]


def _actor(user: dict | None = None) -> dict:
    return user or get_current_user_ctx() or {}


def _can_manage_all(user: dict) -> bool:
    return has_permission(user, "*") or has_permission(user, "approval.manage")


def _visible(rows, user: dict | None = None):
    tid = str(current_tenant_id() or "")
    if not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    u = _actor(user)
    uid = resolve_message_user_id(u)
    out = []
    for r in rows:
        if str(r.get("tenantId", tid)) != tid:
            continue
        if _can_manage_all(u):
            out.append(r)
            continue
        if int(r.get("assigneeId") or 0) == int(uid):
            out.append(r)
    return out


def _matches(row: dict, keyword: str | None = None, biz_type: str | None = None) -> bool:
    if biz_type and row.get("sourceBizType") != biz_type:
        return False
    kw = (keyword or "").strip().lower()
    if not kw:
        return True
    haystack = " ".join(str(row.get(k) or "") for k in (
        "taskId", "title", "applicantName", "sourceBizType", "nodeCode", "nodeName"))
    return kw in haystack.lower()


def _parse_day(raw: str | None, field_label: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", f"{field_label} 必须为 YYYY-MM-DD") from exc


def _db_list(
    page: int,
    page_size: int,
    *,
    user: dict | None,
    processed: bool,
    keyword: str | None = None,
    biz_type: str | None = None,
    result: str | None = None,
    urgency: str | None = None,
    submit_date: str | None = None,
    acted_from: str | None = None,
    acted_to: str | None = None,
) -> tuple[list[dict], int]:
    """审批列表真实服务端查询。所有筛选必须在 COUNT / OFFSET / LIMIT 前进入 SQL。"""
    from sqlalchemy import func, or_, select
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service

    try:
        tenant_id = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tenant_id = 0
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")

    now = datetime.utcnow()
    near_until = now + timedelta(hours=24)
    requested_urgency = str(urgency or "").strip().upper()
    if requested_urgency and requested_urgency not in {"OVERDUE", "NEAR_DEADLINE", "NORMAL"}:
        raise AppException("VALIDATION_ERROR", "不支持的审批紧急度筛选")

    date_start = _parse_day(submit_date, "submitDate")
    date_end = date_start + timedelta(days=1) if date_start is not None else None
    # TP-A05：已办列表按办结时间（acted_at）筛选区间，与待办的 submitDate（created_at）
    # 是两个不同字段，互不复用——已办列表不消费 submitDate，待办列表不消费 acted 区间。
    acted_start = _parse_day(acted_from, "actedFrom")
    acted_end_day = _parse_day(acted_to, "actedTo")
    acted_end = acted_end_day + timedelta(days=1) if acted_end_day is not None else None
    if acted_start is not None and acted_end is not None and acted_start >= acted_end:
        raise AppException("VALIDATION_ERROR", "actedFrom 不能晚于 actedTo")

    with db_service.session() as db:
        statuses = ["APPROVED", "REJECTED", "RETURNED", "TRANSFERRED"] if processed else ["PENDING"]
        if processed and result:
            requested = str(result).strip().upper()
            statuses = [requested] if requested in statuses else ["__NO_MATCH__"]
        cond = [
            WorkflowTask.tenant_id == tenant_id,
            WorkflowTask.is_deleted.is_(False),
            WorkflowTask.status.in_(statuses),
            WorkflowInstance.tenant_id == tenant_id,
            WorkflowInstance.is_deleted.is_(False),
        ]
        if not db_service._can_manage_all_approvals(user):
            cond.append(WorkflowTask.assignee_id == db_service._approval_actor_id(user))
        if biz_type:
            cond.append(WorkflowInstance.source_biz_type == biz_type)
        kw = (keyword or "").strip()
        if kw:
            like = f"%{kw}%"
            search_cond = [
                WorkflowInstance.title.like(like),
                WorkflowInstance.remark.like(like),
                WorkflowInstance.source_biz_type.like(like),
                WorkflowTask.node_code.like(like),
                WorkflowTask.remark.like(like),
            ]
            if kw.isdigit():
                search_cond.append(WorkflowTask.id == int(kw))
            cond.append(or_(*search_cond))

        if not processed and requested_urgency:
            if requested_urgency == "OVERDUE":
                cond.append(WorkflowTask.deadline_at < now)
            elif requested_urgency == "NEAR_DEADLINE":
                cond.extend((WorkflowTask.deadline_at >= now, WorkflowTask.deadline_at <= near_until))
            else:
                cond.append(or_(WorkflowTask.deadline_at.is_(None), WorkflowTask.deadline_at > near_until))
        if not processed and date_start is not None and date_end is not None:
            cond.extend((WorkflowTask.created_at >= date_start, WorkflowTask.created_at < date_end))
        if processed and acted_start is not None:
            cond.append(WorkflowTask.acted_at >= acted_start)
        if processed and acted_end is not None:
            cond.append(WorkflowTask.acted_at < acted_end)

        base = (select(WorkflowTask, WorkflowInstance)
                .join(WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id)
                .where(*cond))
        count_q = (select(func.count()).select_from(WorkflowTask)
                   .join(WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id)
                   .where(*cond))
        total = db.scalar(count_q) or 0
        order = WorkflowTask.acted_at.desc() if processed else WorkflowTask.created_at.asc()
        rows = db.execute(base.order_by(order, WorkflowTask.id)
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [db_service._task_row(task, inst) for task, inst in rows], total


def list_tasks(
    page: int,
    page_size: int,
    status: Optional[str] = None,
    user: dict | None = None,
    keyword: str | None = None,
    biz_type: str | None = None,
    urgency: str | None = None,
    submit_date: str | None = None,
) -> tuple[list[dict], int]:
    if db_enabled():
        # 对外待办只允许 PENDING；历史 status 参数仅保留函数兼容性，不允许绕过待办口径。
        return _db_list(
            page,
            page_size,
            user=user,
            processed=False,
            keyword=keyword,
            biz_type=biz_type,
            urgency=urgency,
            submit_date=submit_date,
        )
    rows = [r for r in _visible(_TASKS, user) if r["status"] == "PENDING"]
    if status:
        rows = [r for r in rows if r["status"] == status]
    rows = [r for r in rows if _matches(r, keyword, biz_type)]
    if urgency:
        rows = [r for r in rows if str(r.get("urgency") or "NORMAL").upper() == str(urgency).upper()]
    if submit_date:
        rows = [r for r in rows if str(r.get("submittedAt") or "").startswith(str(submit_date))]
    return page_slice(rows, page, page_size), len(rows)


def next_pending_task(
    anchor_task_id: str,
    *,
    user: dict | None = None,
    keyword: str | None = None,
    biz_type: str | None = None,
    urgency: str | None = None,
    submit_date: str | None = None,
) -> dict | None:
    """TP-A03/A04：按当前待办队列真实排序（created_at ASC, id ASC）做 seek 查询，
    取锚点任务之后的下一条。不是拿 pageSize=1 重新查第一页去猜"下一条=队首"。"""
    if not db_enabled():
        rows, _ = list_tasks(1, 1, user=user, keyword=keyword, biz_type=biz_type,
                             urgency=urgency, submit_date=submit_date)
        if rows and str(rows[0].get("taskId")) != str(anchor_task_id):
            return rows[0]
        return None

    from sqlalchemy import and_, or_, select
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service

    try:
        tenant_id = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tenant_id = 0
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")

    now = datetime.utcnow()
    near_until = now + timedelta(hours=24)
    requested_urgency = str(urgency or "").strip().upper()
    if requested_urgency and requested_urgency not in {"OVERDUE", "NEAR_DEADLINE", "NORMAL"}:
        raise AppException("VALIDATION_ERROR", "不支持的审批紧急度筛选")
    date_start = _parse_day(submit_date, "submitDate")
    date_end = date_start + timedelta(days=1) if date_start is not None else None

    try:
        anchor_id = int(anchor_task_id)
    except (TypeError, ValueError):
        anchor_id = 0

    with db_service.session() as db:
        cond = [
            WorkflowTask.tenant_id == tenant_id,
            WorkflowTask.is_deleted.is_(False),
            WorkflowTask.status == "PENDING",
            WorkflowInstance.tenant_id == tenant_id,
            WorkflowInstance.is_deleted.is_(False),
        ]
        if not db_service._can_manage_all_approvals(user):
            cond.append(WorkflowTask.assignee_id == db_service._approval_actor_id(user))
        if biz_type:
            cond.append(WorkflowInstance.source_biz_type == biz_type)
        kw = (keyword or "").strip()
        if kw:
            like = f"%{kw}%"
            search_cond = [
                WorkflowInstance.title.like(like),
                WorkflowInstance.remark.like(like),
                WorkflowInstance.source_biz_type.like(like),
                WorkflowTask.node_code.like(like),
                WorkflowTask.remark.like(like),
            ]
            if kw.isdigit():
                search_cond.append(WorkflowTask.id == int(kw))
            cond.append(or_(*search_cond))
        if requested_urgency:
            if requested_urgency == "OVERDUE":
                cond.append(WorkflowTask.deadline_at < now)
            elif requested_urgency == "NEAR_DEADLINE":
                cond.extend((WorkflowTask.deadline_at >= now, WorkflowTask.deadline_at <= near_until))
            else:
                cond.append(or_(WorkflowTask.deadline_at.is_(None), WorkflowTask.deadline_at > near_until))
        if date_start is not None and date_end is not None:
            cond.extend((WorkflowTask.created_at >= date_start, WorkflowTask.created_at < date_end))

        # 锚点任务本身此刻很可能已经不是 PENDING（刚被本次动作办结），所以锚点单独按
        # id 查，不套上面的业务筛选，只用来取它的 created_at/id 定位队列位置。
        anchor = None
        if anchor_id:
            anchor = db.scalars(select(WorkflowTask).where(
                WorkflowTask.id == anchor_id,
                WorkflowTask.tenant_id == tenant_id,
                WorkflowTask.is_deleted.is_(False),
            )).first()
        if anchor is not None:
            cond.append(or_(
                WorkflowTask.created_at > anchor.created_at,
                and_(WorkflowTask.created_at == anchor.created_at, WorkflowTask.id > anchor.id),
            ))

        row = db.execute(
            select(WorkflowTask, WorkflowInstance)
            .join(WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id)
            .where(*cond)
            .order_by(WorkflowTask.created_at.asc(), WorkflowTask.id.asc())
            .limit(1)
        ).first()
        if not row:
            return None
        task, inst = row
        return db_service._task_row(task, inst)


def biz_type_summary(user: dict | None = None) -> list[dict]:
    if db_enabled():
        from app.services import db_service
        return db_service.tasks_by_biz_type(user=user)
    from collections import Counter
    rows = [r for r in _visible(_TASKS, user) if r["status"] == "PENDING"]
    counts = Counter(r["sourceBizType"] for r in rows)
    return [
        {
            "bizType": biz_type,
            "count": count,
            "earliest": min(r["submittedAt"] for r in rows if r["sourceBizType"] == biz_type),
        }
        for biz_type, count in counts.items()
    ]


def get_task(task_id: str, user: dict | None = None) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.get_task(task_id, user=user)
    row = next((r for r in _visible(_TASKS, user) if r["taskId"] == task_id), None)
    if not row:
        raise not_found("审批任务不存在")
    return {**row, "diff": [], "history": [{"action": "SUBMIT", "by": row["applicantName"],
                                            "at": row["submittedAt"]}]}


def _act(task_id: str, action: str, reason: str | None = None, target: str | None = None,
         user: dict | None = None, version: int | None = None) -> dict:
    from app.core.optimistic_lock import require_expected_version
    require_expected_version(version)
    row = next((r for r in _visible(_TASKS, user) if r["taskId"] == task_id), None)
    if not row:
        raise not_found("审批任务不存在")
    if row["status"] != "PENDING":
        raise AppException("APPROVAL_VERSION_CONFLICT", "任务已被处理，请刷新")
    if int(row.get("version") or 0) != int(version):
        raise AppException("APPROVAL_VERSION_CONFLICT", "数据已被他人修改，请刷新后重试")
    row["status"] = action
    row["actedAt"] = _now()
    row["version"] = int(version) + 1
    if reason:
        row["actionReason"] = reason
    if target:
        row["transferTo"] = target
    _PROCESSED.append(row)
    instance_status = {
        "APPROVED": "APPROVED",
        "REJECTED": "REJECTED",
        "RETURNED": "RUNNING",
        "TRANSFERRED": "RUNNING",
    }.get(action, "RUNNING")
    return {"taskId": task_id, "status": action, "actedAt": row["actedAt"],
            "instanceStatus": instance_status, "version": row["version"]}


def approve(task_id: str, comment: str | None, user: dict | None = None,
            version: int | None = None) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.act_task(task_id, "APPROVED", comment, user=user, version=version)
    return _act(task_id, "APPROVED", comment, user=user, version=version)


def return_for_revision(task_id: str, reason: str, user: dict | None = None,
                        version: int | None = None) -> dict:
    """退回修改：当前审批任务完成为 RETURNED，实例保持 RUNNING，并显式进入申请人修改重提节点。

    这与 REJECTED 的终止语义完全分离；后续业务模块可根据实例 current_node/待重提任务完成重提。
    """
    _check_return_reason(reason)
    if not db_enabled():
        return _act(task_id, "RETURNED", reason, user=user, version=version)

    from sqlalchemy import select
    from app.core.optimistic_lock import atomic_versioned_update, require_expected_version
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service
    from app.services import mock_audit_service as audit

    require_expected_version(version)
    with db_service.session() as db:
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == int(task_id),
            WorkflowTask.tenant_id == db_service._tid(),
            WorkflowTask.is_deleted.is_(False),
        )).first()
        if not task:
            raise not_found("审批任务不存在")
        db_service._assert_task_assignee(db, task, user)
        inst = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == task.instance_id,
            WorkflowInstance.tenant_id == db_service._tid(),
            WorkflowInstance.is_deleted.is_(False),
        )).first()
        if not inst:
            raise not_found("审批实例不存在")

        atomic_versioned_update(
            db, WorkflowTask, entity_id=int(task_id), tenant_id=db_service._tid(),
            expected_version=version,
            values={"status": "RETURNED", "acted_at": datetime.utcnow(), "action_reason": reason},
            expected_status="PENDING",
        )
        inst.status = "RUNNING"
        inst.current_node = "APPLICANT_RESUBMIT"
        # 退回后产生独立的“申请人修改重提”工作项，避免把 REJECTED 伪装成可重提。
        db.add(WorkflowTask(
            tenant_id=db_service._tid(),
            instance_id=inst.id,
            node_code="APPLICANT_RESUBMIT",
            assignee_id=inst.applicant_id,
            status="PENDING",
            remark="申请人修改重提",
        ))
        audit.record_critical(
            "审批退回修改", method="POST",
            path=f"/api/v1/approvals/tasks/{task_id}/return",
            status_code=200, target_type="approval", target_id=str(task_id),
            detail={"action": "RETURNED", "reason": reason,
                    "instanceId": str(inst.id), "nextNode": "APPLICANT_RESUBMIT"},
            db=db,
        )
        db.commit()
        return {
            "taskId": str(task_id), "status": "RETURNED",
            "actedAt": _now(), "instanceStatus": "RUNNING",
            "nextNode": "APPLICANT_RESUBMIT", "version": int(version) + 1,
        }


def reject(task_id: str, reason: str, user: dict | None = None,
           version: int | None = None) -> dict:
    _check_reject_reason(reason)
    if db_enabled():
        from app.services import db_service
        return db_service.act_task(task_id, "REJECTED", reason, user=user, version=version)
    return _act(task_id, "REJECTED", reason, user=user, version=version)


def transfer(task_id: str, target_user_id: str, comment: str | None,
             user: dict | None = None, version: int | None = None) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.act_task(task_id, "TRANSFERRED", comment, target_user_id,
                                   user=user, version=version)
    return _act(task_id, "TRANSFERRED", comment, target_user_id, user=user, version=version)


def list_processed(page: int, page_size: int, user: dict | None = None,
                   keyword: str | None = None, biz_type: str | None = None,
                   result: str | None = None, acted_from: str | None = None,
                   acted_to: str | None = None) -> tuple[list[dict], int]:
    if db_enabled():
        return _db_list(page, page_size, user=user, processed=True,
                        keyword=keyword, biz_type=biz_type, result=result,
                        acted_from=acted_from, acted_to=acted_to)
    rows = [r for r in _visible(_PROCESSED, user) if _matches(r, keyword, biz_type)]
    if result:
        rows = [r for r in rows if r.get("status") == str(result).strip().upper()]
    if acted_from:
        rows = [r for r in rows if str(r.get("actedAt") or "") >= str(acted_from)]
    if acted_to:
        rows = [r for r in rows if str(r.get("actedAt") or "")[:10] <= str(acted_to)]
    return page_slice(rows, page, page_size), len(rows)


def list_cc(page: int, page_size: int) -> tuple[list[dict], int]:
    return page_slice(_CC, page, page_size), len(_CC)


def _rule_reason_limits() -> tuple[bool, int]:
    from app.services.platform_service import safe_rule
    try:
        tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tid = 0
    required = bool(safe_rule(tid, "approval", "rejectReasonRequired"))
    min_len = int(safe_rule(tid, "approval", "rejectReasonMinLength") or 0)
    return required, min_len


def _check_reject_reason(reason: str) -> None:
    required, min_len = _rule_reason_limits()
    text = (reason or "").strip()
    if required and len(text) < min_len:
        raise AppException("REJECT_REASON_REQUIRED",
                           f"驳回原因不能少于 {min_len} 字（平台规则中心配置）")


def _check_return_reason(reason: str) -> None:
    required, min_len = _rule_reason_limits()
    text = (reason or "").strip()
    if required and len(text) < min_len:
        raise AppException("RETURN_REASON_REQUIRED",
                           f"退回原因不能少于 {min_len} 字（平台规则中心配置）")
