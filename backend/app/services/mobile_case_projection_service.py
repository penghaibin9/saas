"""V3 §7 「我的办理 / 业务回执中心」投影。

学生问的是「我那件事办到哪一步了、要不要我再做点什么」。V3 之前这条链路是
``mobile_student_service.my_applications()``：三张表各自 ``.all()`` 全量读回 Python
再拼列表——没有分页、没有游标、状态过滤也在 Python 里做。学校有 5 万条历史办理时，
学生每打开一次「我的申请」就是三次全表扫描（V3 深审 P0-06）。

本模块的三条硬约束：

1. **不新建统一事实表。** 每条 case 都保留自己的 source identity
   （sourceModule / sourceBizType / sourceBizId），状态仍以各域为准。
2. **分页在数据库里做。** 三个来源用 UNION ALL 归一成同一投影，按
   ``(updated_at, source, id)`` keyset 下推排序与分页，禁止 ``.all()`` → Python slice，
   也禁止深 OFFSET。
3. **动作回原业务。** 退回重提之类的动作由 MobileAction 指回原业务页，
   不在这里复制任何业务状态机。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, cast, func, literal, or_, select, union_all

from app.core.exceptions import AppException
from app.services import mobile_action_service as action_svc
from app.services.db_service import _iso, _tid, session

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 50

#: §7.1 四个分段。每个分段直接翻译成 SQL 的状态集合，过滤全部下推。
STATUS_GROUPS: dict[str, tuple[str, ...]] = {
    # 学生自己还要动手的：草稿、待补材料
    "pending": ("DRAFT", "PENDING_SUPPLEMENT", "PENDING_MATERIAL"),
    # 已被退回/驳回/作废——退回重提的入口就在这一组
    "returned": ("RETURNED", "REJECTED", "VOIDED"),
    # 办结
    "done": ("APPROVED", "COMPLETED", "CLOSED", "PASSED", "GRANTED"),
}
#: “审批中”= 不属于上面任何一组的其余状态，用 NOT IN 下推，避免枚举不全就漏条。
PROCESSING_GROUP = "processing"
ALL_GROUP = "all"

GROUP_LABELS = {
    "pending": "待处理",
    PROCESSING_GROUP: "审批中",
    "returned": "退回",
    "done": "已完成",
}

#: source key → (业务模块, 业务类型, 展示前缀, 承办部门, 学生端 action)
_SOURCE_META = {
    "LEAVE": ("student-affairs", "LEAVE", "学生请假", "学工处", "student.leave.detail", "leaveId"),
    "GRANT": ("student-affairs", "GRANT", "资助申请", "资助中心", None, None),
    "WORKORDER": ("campus-service", "WORKORDER", "校园服务", "服务中心", None, None),
}


def _normalized_statuses() -> set[str]:
    known: set[str] = set()
    for values in STATUS_GROUPS.values():
        known.update(values)
    return known


def _group_of(status: str | None) -> str:
    value = str(status or "").upper()
    for group, values in STATUS_GROUPS.items():
        if value in values:
            return group
    return PROCESSING_GROUP


def _source_selects(student_id: int, cs_student_id: int | None):
    """三个来源归一成同一列形状，供 UNION ALL 下推排序分页。"""
    from app.models import CsGrant, CsLeave, CsServiceStudent, CsWorkOrder  # noqa: F401

    def _columns(source: str, model, subject, status, apply_time, handler, opinion, code):
        return (
            literal(source).label("source"),
            model.id.label("biz_id"),
            cast(code, String(50)).label("code"),
            cast(subject, String(200)).label("subject"),
            cast(status, String(50)).label("status"),
            apply_time.label("apply_time"),
            model.updated_at.label("updated_at"),
            cast(handler, String(100)).label("handler"),
            cast(opinion, String(500)).label("opinion"),
        )

    # t_cs_leave 双状态列并行：13A 新提交只挂 student_id，老 campus-service 提交只挂
    # cs_student_id。两条线都要查，漏掉任何一条都会让学生看不到自己的请假。
    leave_owner = [CsLeave.student_id == student_id]
    if cs_student_id:
        leave_owner.append(CsLeave.cs_student_id == cs_student_id)
    leave = select(*_columns(
        "LEAVE", CsLeave, CsLeave.leave_type,
        func.coalesce(CsLeave.affairs_status, CsLeave.status),
        CsLeave.apply_time, CsLeave.reviewer, CsLeave.return_reason, CsLeave.code,
    )).where(
        CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False), or_(*leave_owner),
    )

    selects = [leave]
    if cs_student_id:
        selects.append(select(*_columns(
            "GRANT", CsGrant, CsGrant.grant_type, CsGrant.status,
            CsGrant.apply_time, CsGrant.reviewer, CsGrant.return_reason, CsGrant.code,
        )).where(
            CsGrant.tenant_id == _tid(), CsGrant.is_deleted.is_(False),
            CsGrant.cs_student_id == cs_student_id,
        ))
        selects.append(select(*_columns(
            "WORKORDER", CsWorkOrder, CsWorkOrder.title, CsWorkOrder.status,
            literal(None), CsWorkOrder.handler, literal(None), CsWorkOrder.code,
        )).where(
            CsWorkOrder.tenant_id == _tid(), CsWorkOrder.is_deleted.is_(False),
            CsWorkOrder.cs_student_id == cs_student_id,
        ))
    return selects


def _apply_group(stmt, group: str):
    """状态分组过滤下推到 SQL，不在 Python 里筛。"""
    column = stmt.selected_columns.status
    if group == ALL_GROUP:
        return stmt
    if group == PROCESSING_GROUP:
        # 审批中 = 其余状态。用 NOT IN 而不是枚举，新增中间态不会被悄悄漏掉。
        return stmt.where(func.upper(column).notin_(sorted(_normalized_statuses())))
    values = STATUS_GROUPS.get(group)
    if not values:
        raise AppException("VALIDATION_ERROR", f"未知的办理分组：{group}")
    return stmt.where(func.upper(column).in_(values))


def _cursor_of(updated_at: datetime | None, source: str, biz_id: int) -> str:
    stamp = updated_at.isoformat(timespec="microseconds") if updated_at else "0000"
    return f"{stamp}|{source}|{biz_id}"


def _apply_cursor(stmt, cursor: str | None):
    """keyset 游标：(updated_at, source, id) 降序，严格小于上一页最后一条。"""
    if not cursor:
        return stmt
    parts = str(cursor).split("|")
    if len(parts) != 3:
        raise AppException("VALIDATION_ERROR", "游标格式无效")
    stamp, source, biz_id = parts
    try:
        last_updated = datetime.fromisoformat(stamp)
        last_id = int(biz_id)
    except ValueError:
        raise AppException("VALIDATION_ERROR", "游标格式无效")
    columns = stmt.selected_columns
    return stmt.where(
        (columns.updated_at < last_updated)
        | ((columns.updated_at == last_updated) & (columns.source > source))
        | ((columns.updated_at == last_updated) & (columns.source == source) & (columns.biz_id < last_id))
    )


def _case_row(row) -> dict[str, Any]:
    module, biz_type, prefix, dept, action_key, action_param = _SOURCE_META.get(
        row.source, ("student-affairs", row.source, row.source, "", None, None)
    )
    status = str(row.status or "")
    group = _group_of(status)
    subject = str(row.subject or "").strip()
    title = f"{prefix}（{subject}）" if subject and row.source != "WORKORDER" else (subject or prefix)
    action = None
    if action_key and action_param:
        action = action_svc.build_message_action(
            action_key, {action_param: str(row.biz_id)},
            client=action_svc.CLIENT_STUDENT_MINI,
        )
    return {
        "caseId": f"{row.source.lower()}:{row.biz_id}",
        "sourceModule": module,
        "sourceBizType": biz_type,
        "sourceBizId": str(row.biz_id),
        "no": row.code or f"{row.source[:2]}{row.biz_id}",
        "title": title,
        "status": status,
        "statusGroup": group,
        "statusLabel": GROUP_LABELS.get(group, group),
        "dept": dept,
        "handler": row.handler or "待分配",
        "latestOpinion": row.opinion or "",
        "applyTime": _iso(row.apply_time) if row.apply_time else None,
        "updatedAt": _iso(row.updated_at) if row.updated_at else None,
        "action": action,
        "cursor": _cursor_of(row.updated_at, row.source, int(row.biz_id)),
    }


def list_my_cases(user: dict, *, status_group: str = ALL_GROUP, cursor: str | None = None,
                  page_size: int = PAGE_SIZE_DEFAULT) -> dict[str, Any]:
    """本人办理列表。分页与状态过滤全部在数据库里完成。"""
    from app.db.session import db_enabled
    from app.services.mobile_student_service import _require_student, resolve_student

    current = _require_student(user)
    group = str(status_group or ALL_GROUP).lower()
    if group not in {ALL_GROUP, PROCESSING_GROUP} and group not in STATUS_GROUPS:
        raise AppException("VALIDATION_ERROR", f"未知的办理分组：{status_group}")
    size = max(1, min(PAGE_SIZE_MAX, int(page_size or PAGE_SIZE_DEFAULT)))

    tabs = [{"key": ALL_GROUP, "label": "全部"}] + [
        {"key": key, "label": GROUP_LABELS[key]}
        for key in ("pending", PROCESSING_GROUP, "returned", "done")
    ]
    if not db_enabled():
        return {"tabs": tabs, "tab": group, "items": [], "nextCursor": None, "hasData": False}

    with session() as db:
        student = resolve_student(db, current)
        if not student:
            return {"tabs": tabs, "tab": group, "items": [], "nextCursor": None, "hasData": False}
        from app.models import CsServiceStudent
        from app.services.mobile_student_service import _resolve_domain_student
        cs = _resolve_domain_student(db, CsServiceStudent, student)

        unioned = union_all(*_source_selects(student.id, cs.id if cs else None)).subquery()
        stmt = select(
            unioned.c.source, unioned.c.biz_id, unioned.c.code, unioned.c.subject,
            unioned.c.status, unioned.c.apply_time, unioned.c.updated_at,
            unioned.c.handler, unioned.c.opinion,
        )
        stmt = _apply_group(stmt, group)
        stmt = _apply_cursor(stmt, cursor)
        # pageSize+1 判定 hasMore，后续页不重复 COUNT（§11.2）。
        stmt = stmt.order_by(
            unioned.c.updated_at.desc(), unioned.c.source.asc(), unioned.c.biz_id.desc()
        ).limit(size + 1)
        rows = db.execute(stmt).all()

    has_more = len(rows) > size
    page = [_case_row(row) for row in rows[:size]]
    return {
        "tabs": tabs,
        "tab": group,
        "items": page,
        "nextCursor": page[-1]["cursor"] if has_more and page else None,
        "hasData": True,
    }


def get_my_case(user: dict, *, case_id: str) -> dict[str, Any]:
    """单条办理详情 + 时间线。

    时间线可以从 workflow task / 域事件聚合，但每个节点都保留自己的 source identity，
    不合并成一段没有出处的叙述。
    """
    from app.db.session import db_enabled
    from app.services.mobile_student_service import _require_student, resolve_student

    current = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持")
    raw = str(case_id or "").strip()
    if ":" not in raw:
        raise AppException("VALIDATION_ERROR", "办理单号无效")
    source, _, biz_id = raw.partition(":")
    source = source.upper()
    if source not in _SOURCE_META or not biz_id.isdigit():
        raise AppException("VALIDATION_ERROR", "办理单号无效")

    with session() as db:
        student = resolve_student(db, current)
        if not student:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        from app.models import CsServiceStudent
        from app.services.mobile_student_service import _resolve_domain_student
        cs = _resolve_domain_student(db, CsServiceStudent, student)

        unioned = union_all(*_source_selects(student.id, cs.id if cs else None)).subquery()
        row = db.execute(
            select(
                unioned.c.source, unioned.c.biz_id, unioned.c.code, unioned.c.subject,
                unioned.c.status, unioned.c.apply_time, unioned.c.updated_at,
                unioned.c.handler, unioned.c.opinion,
            ).where(unioned.c.source == source, unioned.c.biz_id == int(biz_id))
        ).first()
        # 归属校验就在 UNION 的 owner 条件里：不是本人的记录根本不在结果集中，
        # 因此这里返回 404 而不是 403，不泄露他人记录是否存在。
        if row is None:
            raise AppException("DATA_NOT_FOUND", "办理记录不存在")

        detail = _case_row(row)
        detail["timeline"] = _timeline(db, source, int(biz_id), row)
    return detail


def _timeline(db, source: str, biz_id: int, row) -> list[dict[str, Any]]:
    """节点来源：workflow 实例任务优先；没有实例时退回域自身的申请/处理时间。"""
    from app.models import WorkflowInstance, WorkflowTask

    nodes: list[dict[str, Any]] = []
    if row.apply_time:
        nodes.append({
            "nodeCode": "SUBMITTED", "label": "提交申请", "status": "DONE",
            "actor": None, "opinion": None, "at": _iso(row.apply_time),
            "source": f"{source.lower()}:{biz_id}",
        })

    module, biz_type, *_ = _SOURCE_META[source]
    instance = db.scalars(
        select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.is_deleted.is_(False),
            WorkflowInstance.source_module == module,
            WorkflowInstance.source_biz_type == biz_type,
            WorkflowInstance.source_biz_id == biz_id,
        ).order_by(WorkflowInstance.id.desc()).limit(1)
    ).first()
    if instance is not None:
        tasks = db.scalars(
            select(WorkflowTask).where(
                WorkflowTask.tenant_id == _tid(),
                WorkflowTask.is_deleted.is_(False),
                WorkflowTask.instance_id == instance.id,
            ).order_by(WorkflowTask.id.asc()).limit(50)
        ).all()
        for task in tasks:
            nodes.append({
                "nodeCode": task.node_code, "label": task.node_code or "审批",
                "status": task.status,
                "actor": None,  # 审批人姓名属于他人信息，列表投影不下发
                "opinion": task.action_reason or task.remark or None,
                "at": _iso(task.acted_at) if task.acted_at else None,
                "source": f"workflow-task:{task.id}",
            })
    elif row.opinion or row.handler:
        # 没有 workflow 实例的历史单据：至少把域自身记录的处理意见作为一个节点，
        # 但明确标出它的出处，不伪装成审批流节点。
        nodes.append({
            "nodeCode": "DOMAIN_REVIEW", "label": "处理意见", "status": str(row.status or ""),
            "actor": None, "opinion": row.opinion or None,
            "at": _iso(row.updated_at) if row.updated_at else None,
            "source": f"{source.lower()}:{biz_id}",
        })
    return nodes


def case_contract_snapshot() -> dict[str, Any]:
    return {
        "pageSizeDefault": PAGE_SIZE_DEFAULT,
        "pageSizeMax": PAGE_SIZE_MAX,
        "groups": [ALL_GROUP, "pending", PROCESSING_GROUP, "returned", "done"],
        "sources": sorted(_SOURCE_META),
        "cursorKey": "updated_at|source|biz_id",
    }
