"""审批退回台账查询：所有筛选在 COUNT / OFFSET / LIMIT 之前进入数据库。"""
from __future__ import annotations

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import db_enabled


_RESUBMIT_NODE = "APPLICANT_RESUBMIT"
_RECTIFY_STATUSES = {"PENDING_RESUBMIT", "RESUBMITTED", "CLOSED"}


def _require_db() -> None:
    if not db_enabled():
        raise AppException(
            "APPROVAL_BACKEND_UNAVAILABLE",
            "审批中心需要真实数据库，当前不可展示演示数据或产生假成功",
            http_status=503,
        )


def _tenant_id() -> int:
    try:
        value = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        value = 0
    if not value:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文", http_status=400)
    return value


def _rectify_status(instance_status: str | None, current_node: str | None) -> str:
    status = str(instance_status or "").upper()
    node = str(current_node or "").upper()
    if status == "RUNNING" and node == _RESUBMIT_NODE:
        return "PENDING_RESUBMIT"
    if status == "RUNNING":
        return "RESUBMITTED"
    return "CLOSED"


def list_returned(
    page: int,
    page_size: int,
    *,
    user=None,
    keyword: str | None = None,
    rectify_status: str | None = None,
):
    """返回本人可见的 RETURNED 任务，整改状态筛选与 total 均以全库命中集为准。"""
    _require_db()
    from sqlalchemy import and_, func, or_, select
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service

    tenant_id = _tenant_id()
    wanted = str(rectify_status or "").strip().upper()
    if wanted and wanted not in _RECTIFY_STATUSES:
        raise AppException("VALIDATION_ERROR", "未知退回整改状态", http_status=400)

    cond = [
        WorkflowTask.tenant_id == tenant_id,
        WorkflowTask.is_deleted.is_(False),
        WorkflowTask.status == "RETURNED",
        WorkflowInstance.tenant_id == tenant_id,
        WorkflowInstance.is_deleted.is_(False),
    ]
    if not db_service._can_manage_all_approvals(user):
        cond.append(WorkflowTask.assignee_id == db_service._approval_actor_id(user))

    kw = str(keyword or "").strip()
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

    if wanted == "PENDING_RESUBMIT":
        cond.append(and_(
            WorkflowInstance.status == "RUNNING",
            WorkflowInstance.current_node == _RESUBMIT_NODE,
        ))
    elif wanted == "RESUBMITTED":
        cond.append(and_(
            WorkflowInstance.status == "RUNNING",
            or_(
                WorkflowInstance.current_node.is_(None),
                WorkflowInstance.current_node != _RESUBMIT_NODE,
            ),
        ))
    elif wanted == "CLOSED":
        cond.append(or_(
            WorkflowInstance.status.is_(None),
            WorkflowInstance.status != "RUNNING",
        ))

    joined = WorkflowTask.__table__.join(
        WorkflowInstance.__table__,
        WorkflowInstance.id == WorkflowTask.instance_id,
    )
    count_q = select(func.count()).select_from(joined).where(*cond)
    data_q = (
        select(WorkflowTask, WorkflowInstance)
        .join(WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id)
        .where(*cond)
        .order_by(WorkflowTask.acted_at.desc(), WorkflowTask.id.desc())
        .offset((max(1, int(page)) - 1) * int(page_size))
        .limit(int(page_size))
    )

    with db_service.session() as db:
        total = int(db.scalar(count_q) or 0)
        records = db.execute(data_q).all()
        rows = []
        for task, inst in records:
            row = db_service._task_row(task, inst)
            row["instanceStatus"] = inst.status or ""
            row["currentInstanceNode"] = inst.current_node or ""
            row["sourceBizId"] = str(inst.source_biz_id or "")
            row["rectifyStatus"] = _rectify_status(inst.status, inst.current_node)
            row["allowedActions"] = []
            rows.append(row)
        return rows, total
