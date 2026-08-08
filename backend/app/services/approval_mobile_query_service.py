"""Stage B / B2 教师小程序审批队列查询。

只读真实数据库，统一提供 pending / done / mine 三类真分页；搜索在数据库 WHERE
阶段完成，支持姓名、学号、审批任务号、业务单号与标题。正式链路禁止内存 fallback。
"""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import db_enabled


def _require_db() -> None:
    if not db_enabled():
        raise AppException(
            "APPROVAL_BACKEND_UNAVAILABLE",
            "审批中心需要真实数据库，当前不可展示演示数据",
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


def _actor_id(user) -> int:
    from app.services import db_service

    try:
        value = int(db_service._approval_actor_id(user) or 0)
    except (TypeError, ValueError):
        value = 0
    if not value:
        raise AppException("APPROVAL_ACTOR_REQUIRED", "当前账号无法解析审批身份", http_status=403)
    return value


def _task_row(task, inst, profile=None) -> dict:
    return {
        "taskId": str(task.id),
        "instanceId": str(inst.id),
        "version": int(task.version or 0),
        "title": inst.title or "审批任务",
        "sourceModule": inst.source_module or "",
        "sourceBizType": inst.source_biz_type or "",
        "sourceBizId": str(inst.source_biz_id or ""),
        "applicantName": getattr(profile, "real_name", None) or "申请人",
        "studentNo": getattr(profile, "student_no", None) or "",
        "nodeCode": task.node_code or "",
        "nodeName": task.node_code or "当前审批",
        "status": task.status,
        "submittedAt": task.created_at.isoformat(timespec="seconds") if task.created_at else None,
        "actedAt": task.acted_at.isoformat(timespec="seconds") if task.acted_at else None,
        "deadlineAt": task.deadline_at.isoformat(timespec="seconds") if task.deadline_at else None,
        "allowedActions": ["APPROVE", "RETURN", "REJECT", "TRANSFER"] if task.status == "PENDING" else [],
    }


def _instance_row(inst, profile=None) -> dict:
    return {
        "taskId": str(inst.id),
        "instanceId": str(inst.id),
        "version": int(inst.version or 0),
        "title": inst.title or "审批申请",
        "sourceModule": inst.source_module or "",
        "sourceBizType": inst.source_biz_type or "",
        "sourceBizId": str(inst.source_biz_id or ""),
        "applicantName": getattr(profile, "real_name", None) or "我",
        "studentNo": getattr(profile, "student_no", None) or "",
        "nodeCode": inst.current_node or "",
        "nodeName": inst.current_node or "当前节点",
        "status": inst.status,
        "submittedAt": inst.created_at.isoformat(timespec="seconds") if inst.created_at else None,
        "actedAt": inst.updated_at.isoformat(timespec="seconds") if inst.updated_at else None,
        "deadlineAt": None,
        "allowedActions": [],
    }


def list_queue(
    mode: str,
    page: int,
    page_size: int,
    *,
    user=None,
    keyword: str | None = None,
    biz_type: str | None = None,
) -> tuple[list[dict], int]:
    """返回教师审批队列。

    mode=pending: 待我审批；mode=done: 我已处理；mode=mine: 我发起的。
    所有筛选均先 WHERE / COUNT，再 OFFSET / LIMIT，保证跨页 total 正确。
    """
    _require_db()
    normalized = str(mode or "pending").strip().lower()
    if normalized not in {"pending", "done", "mine"}:
        raise AppException("INVALID_APPROVAL_QUEUE", "不支持的审批队列", http_status=422)

    from app.models import StudentAccountLink, StudentProfile, WorkflowInstance, WorkflowTask
    from app.models.student_account_link import LINK_ACTIVE
    from app.services import db_service

    tid = _tenant_id()
    actor = _actor_id(user)
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 100))
    kw = str(keyword or "").strip()

    with db_service.session() as db:
        if normalized == "mine":
            cond = [
                WorkflowInstance.tenant_id == tid,
                WorkflowInstance.is_deleted.is_(False),
                WorkflowInstance.applicant_id == actor,
            ]
            if biz_type:
                cond.append(WorkflowInstance.source_biz_type == biz_type)
            if kw:
                like = f"%{kw}%"
                search = [
                    WorkflowInstance.title.like(like),
                    WorkflowInstance.source_biz_type.like(like),
                    WorkflowInstance.remark.like(like),
                ]
                if kw.isdigit():
                    search.extend([
                        WorkflowInstance.id == int(kw),
                        WorkflowInstance.source_biz_id == int(kw),
                    ])
                cond.append(or_(*search))

            total = int(db.scalar(
                select(func.count()).select_from(WorkflowInstance).where(*cond)
            ) or 0)
            rows = db.scalars(
                select(WorkflowInstance)
                .where(*cond)
                .order_by(WorkflowInstance.created_at.desc(), WorkflowInstance.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return [_instance_row(inst) for inst in rows], total

        statuses = ["PENDING"] if normalized == "pending" else ["APPROVED", "REJECTED", "RETURNED", "TRANSFERRED"]
        cond = [
            WorkflowTask.tenant_id == tid,
            WorkflowTask.is_deleted.is_(False),
            WorkflowTask.status.in_(statuses),
            WorkflowInstance.tenant_id == tid,
            WorkflowInstance.is_deleted.is_(False),
        ]
        if not db_service._can_manage_all_approvals(user):
            cond.append(WorkflowTask.assignee_id == actor)
        if biz_type:
            cond.append(WorkflowInstance.source_biz_type == biz_type)

        # StudentAccountLink 是 applicant user_id -> StudentProfile 的稳定绑定；outer join
        # 保证教师/职工发起的流程不会因为没有学生档案而被过滤掉。
        joins = (
            WorkflowTask.__table__
            .join(WorkflowInstance.__table__, WorkflowInstance.id == WorkflowTask.instance_id)
            .outerjoin(
                StudentAccountLink.__table__,
                (StudentAccountLink.tenant_id == tid)
                & (StudentAccountLink.user_id == WorkflowInstance.applicant_id)
                & (StudentAccountLink.link_status == LINK_ACTIVE)
                & (StudentAccountLink.is_deleted.is_(False)),
            )
            .outerjoin(
                StudentProfile.__table__,
                (StudentProfile.tenant_id == tid)
                & (StudentProfile.id == StudentAccountLink.student_id)
                & (StudentProfile.is_deleted.is_(False)),
            )
        )
        if kw:
            like = f"%{kw}%"
            search = [
                WorkflowInstance.title.like(like),
                WorkflowInstance.source_biz_type.like(like),
                WorkflowInstance.remark.like(like),
                WorkflowTask.node_code.like(like),
                WorkflowTask.remark.like(like),
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
            ]
            if kw.isdigit():
                search.extend([
                    WorkflowTask.id == int(kw),
                    WorkflowInstance.id == int(kw),
                    WorkflowInstance.source_biz_id == int(kw),
                ])
            cond.append(or_(*search))

        total = int(db.scalar(select(func.count()).select_from(joins).where(*cond)) or 0)
        order = WorkflowTask.created_at.asc() if normalized == "pending" else WorkflowTask.acted_at.desc()
        rows = db.execute(
            select(WorkflowTask, WorkflowInstance, StudentProfile)
            .select_from(joins)
            .where(*cond)
            .order_by(order, WorkflowTask.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [_task_row(task, inst, profile) for task, inst, profile in rows], total
