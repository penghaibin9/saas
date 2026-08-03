"""学工四端学生业务合同。

在不删除旧字段的前提下，为学生 PC/小程序统一补齐：
- allowedActions（后端唯一动作源）；
- 我的申请通用 DTO；
- 当前节点/责任人/期限；
- 真实审计时间线；
- 本人材料版本元数据；
- 消息 actionKey/actionParams。
"""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select

from app.services.db_service import _iso, _tid, session

_INSTALLED = False

_ACTION_LABELS = {
    "EDIT_RETURNED": "修改退回内容",
    "RESUBMIT": "重新提交",
    "SUBMIT_CANCEL": "申请销假",
    "SUBMIT_EXTENSION": "申请续假",
    "SUBMIT_OBJECTION": "提交异议",
    "SUBMIT_APPEAL": "提交申诉",
    "WITHDRAW": "撤回申请",
}
_NODE_LABELS = {
    "CLASS_REVIEW": "班级评议",
    "COUNSELOR_REVIEW": "辅导员审批",
    "COLLEGE_REVIEW": "学院审批",
    "SCHOOL_REVIEW": "学校审批",
    "STUDENT_AFFAIRS_REVIEW": "学工处审批",
    "DORM_MANAGER_REVIEW": "宿管审批",
    "PUBLICITY": "公示",
}
_ACTION_KEY_BY_BIZ = {
    "LEAVE": "AFFAIRS_LEAVE",
    "AID": "AFFAIRS_AID",
    "FUNDING": "AFFAIRS_FUNDING",
    "DISCIPLINE": "AFFAIRS_DISCIPLINE",
    "DISCIPLINE_APPEAL": "AFFAIRS_DISCIPLINE",
    "DORM": "AFFAIRS_DORM",
    "DORM_TRANSFER": "AFFAIRS_DORM",
    "SECOND_CLASS": "AFFAIRS_ACTIVITY",
    "CREDIT_APPEAL": "AFFAIRS_ACTIVITY",
    "ACTIVITY": "AFFAIRS_ACTIVITY",
    "WORKORDER": "AFFAIRS_APPLICATIONS",
    "GRANT": "AFFAIRS_APPLICATIONS",
}
_DONE = {"APPROVED", "COMPLETED", "CLOSED", "PASSED", "GRANTED", "EXECUTED", "ARCHIVED", "REVOKED"}
_REJECTED = {"REJECTED", "RETURNED", "VOIDED", "CANCELLED", "WITHDRAWN", "UPHELD"}


def _biz(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_")


def _safe_actions(value: Any, fallback: Iterable[str] = ()) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return list(dict.fromkeys(str(x).strip().upper() for x in value if str(x).strip()))
    return list(dict.fromkeys(str(x).strip().upper() for x in fallback if str(x).strip()))


def _status_group(status: Any, actions: Iterable[str] = ()) -> str:
    state = str(status or "").upper()
    action_set = set(actions or ())
    if state in _DONE:
        return "done"
    if state in _REJECTED or {"EDIT_RETURNED", "RESUBMIT"}.intersection(action_set):
        return "rejected"
    return "processing"


def _next_action(status: Any, actions: list[str], handler: str = "") -> dict:
    priority = (
        "EDIT_RETURNED", "RESUBMIT", "SUBMIT_CANCEL", "SUBMIT_EXTENSION",
        "SUBMIT_OBJECTION", "SUBMIT_APPEAL", "WITHDRAW",
    )
    for key in priority:
        if key in actions:
            return {"key": key, "label": _ACTION_LABELS[key], "actor": "STUDENT"}
    group = _status_group(status, actions)
    if group == "processing":
        return {"key": "WAIT", "label": f"等待{handler or '当前责任人'}处理", "actor": "STAFF"}
    return {"key": "VIEW_RESULT", "label": "查看办理结果", "actor": "STUDENT"}


def _workflow_context(db, *, biz_type: str, biz_id: int, workflow_id: int | None = None) -> dict:
    from app.models import UnifiedTodo, User, WorkflowInstance, WorkflowTask

    workflow = db.get(WorkflowInstance, int(workflow_id)) if workflow_id else None
    if workflow and (workflow.is_deleted or workflow.tenant_id != _tid()):
        workflow = None
    if workflow is None:
        variants = {biz_type, biz_type.lower(), biz_type.replace("_", "-").lower()}
        workflow = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == _tid(),
            WorkflowInstance.source_module == "student-affairs",
            WorkflowInstance.source_biz_type.in_(variants),
            WorkflowInstance.source_biz_id == int(biz_id),
            WorkflowInstance.is_deleted.is_(False),
        ).order_by(WorkflowInstance.id.desc())).first()

    task = None
    if workflow:
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(),
            WorkflowTask.instance_id == int(workflow.id),
            WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False),
        ).order_by(WorkflowTask.id.desc())).first()

    variants = {biz_type, biz_type.lower(), biz_type.replace("_", "-").lower()}
    todo = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_type.in_(variants),
        UnifiedTodo.source_biz_id == int(biz_id),
        UnifiedTodo.status == "PENDING",
        UnifiedTodo.is_deleted.is_(False),
    ).order_by(UnifiedTodo.id.desc())).first()

    assignee_id = int((task.assignee_id if task else None) or (todo.assignee_id if todo else 0) or 0)
    assignee = db.get(User, assignee_id) if assignee_id else None
    if assignee and (assignee.is_deleted or assignee.tenant_id != _tid()):
        assignee = None
    node = (workflow.current_node if workflow else None) or (task.node_code if task else None) or ""
    due_at = (task.deadline_at if task else None) or (todo.due_at if todo else None)
    return {
        "workflowId": str(workflow.id) if workflow else "",
        "workflowStatus": workflow.status if workflow else "",
        "currentNode": node,
        "currentNodeLabel": _NODE_LABELS.get(node, node),
        "handlerId": str(assignee_id) if assignee_id else "",
        "handler": (assignee.real_name if assignee else "") or "待分配",
        "dueAt": _iso(due_at),
    }


def _timeline(db, *, biz_type: str, biz_id: int, created_at=None) -> list[dict]:
    from app.models import AffairsAuditTrail

    rows = db.scalars(select(AffairsAuditTrail).where(
        AffairsAuditTrail.tenant_id == _tid(),
        AffairsAuditTrail.biz_type == biz_type,
        AffairsAuditTrail.biz_id == int(biz_id),
    ).order_by(AffairsAuditTrail.occurred_at, AffairsAuditTrail.id)).all()
    items: list[dict] = []
    if created_at and (not rows or created_at < rows[0].occurred_at):
        items.append({
            "eventId": f"created-{biz_type}-{biz_id}", "action": "CREATED", "actionLabel": "申请创建",
            "operator": "学生本人", "role": "STUDENT", "occurredAt": _iso(created_at),
            "description": "申请已创建", "fromStatus": "", "toStatus": "", "attachments": [],
        })
    for row in rows:
        items.append({
            "eventId": str(row.id), "action": row.action,
            "actionLabel": _ACTION_LABELS.get(row.action, row.action),
            "operator": row.operator or "系统", "role": row.role_name or "",
            "occurredAt": _iso(row.occurred_at), "description": row.detail or "",
            "fromStatus": row.before_val or "", "toStatus": row.after_val or "", "attachments": [],
        })
    return items


def _materials(db, *, biz_types: Iterable[str], biz_id: int, status: str) -> dict:
    from app.models import AffairsAttachment

    variants = {_biz(x) for x in biz_types if x}
    rows = db.scalars(select(AffairsAttachment).where(
        AffairsAttachment.tenant_id == _tid(),
        AffairsAttachment.biz_type.in_(variants or {"__NONE__"}),
        AffairsAttachment.biz_id == int(biz_id),
    ).order_by(AffairsAttachment.created_at.desc(), AffairsAttachment.id.desc())).all()
    data = [{
        "attachmentId": str(row.id),
        "fileId": str(row.file_id) if not row.is_deleted else "",
        "fileName": row.file_name or "材料附件",
        "note": row.note or "",
        "version": int(row.version or 0),
        "uploadedAt": _iso(row.created_at),
        "active": not bool(row.is_deleted),
        "downloadable": not bool(row.is_deleted),
    } for row in rows]
    current = [item for item in data if item["active"]]
    history = [item for item in data if not item["active"]]
    returned = str(status or "").upper() in {"DRAFT", "RETURNED"}
    return {
        "current": current,
        "history": history,
        "currentCount": len(current),
        "historyCount": len(history),
        "missingItems": [],
        "missingItemsKnown": False,
        "supplementStatus": "PENDING_STUDENT_EDIT" if returned else "NOT_PENDING",
    }



def _empty_workflow_context() -> dict:
    return {
        "workflowId": "", "workflowStatus": "", "currentNode": "",
        "currentNodeLabel": "", "handlerId": "", "handler": "待分配", "dueAt": None,
    }


def _batch_workflow_contexts(db, specs: list[dict]) -> dict[str, dict]:
    """批量解析流程、待办和责任人，查询次数不随申请条数增长。"""
    from app.models import UnifiedTodo, User, WorkflowInstance, WorkflowTask

    if not specs:
        return {}
    tenant_id = _tid()
    direct_ids = {int(spec["workflow_id"]) for spec in specs if spec.get("workflow_id")}
    workflows_by_id = {}
    if direct_ids:
        workflows_by_id = {
            int(row.id): row for row in db.scalars(select(WorkflowInstance).where(
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.id.in_(direct_ids),
                WorkflowInstance.is_deleted.is_(False),
            )).all()
        }

    unresolved_ids = {int(spec["biz_id"]) for spec in specs if not workflows_by_id.get(int(spec.get("workflow_id") or 0))}
    fallback_rows = []
    if unresolved_ids:
        fallback_rows = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == tenant_id,
            WorkflowInstance.source_module == "student-affairs",
            WorkflowInstance.source_biz_id.in_(unresolved_ids),
            WorkflowInstance.is_deleted.is_(False),
        ).order_by(WorkflowInstance.id.desc())).all()

    workflows: dict[str, Any] = {}
    for spec in specs:
        workflow = workflows_by_id.get(int(spec.get("workflow_id") or 0))
        if workflow is None:
            wanted_type = _biz(spec["biz_type"])
            wanted_id = int(spec["biz_id"])
            workflow = next((row for row in fallback_rows if int(row.source_biz_id) == wanted_id
                             and _biz(row.source_biz_type) == wanted_type), None)
        workflows[spec["key"]] = workflow

    workflow_ids = {int(row.id) for row in workflows.values() if row is not None}
    task_by_instance = {}
    if workflow_ids:
        for row in db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == tenant_id,
            WorkflowTask.instance_id.in_(workflow_ids),
            WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False),
        ).order_by(WorkflowTask.id.desc())).all():
            task_by_instance.setdefault(int(row.instance_id), row)

    biz_ids = {int(spec["biz_id"]) for spec in specs}
    todo_rows = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == tenant_id,
        UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id.in_(biz_ids),
        UnifiedTodo.status == "PENDING",
        UnifiedTodo.is_deleted.is_(False),
    ).order_by(UnifiedTodo.id.desc())).all()
    todo_by_key = {}
    for spec in specs:
        wanted = (_biz(spec["biz_type"]), int(spec["biz_id"]))
        todo_by_key[spec["key"]] = next((row for row in todo_rows
                                         if (_biz(row.source_biz_type), int(row.source_biz_id)) == wanted), None)

    assignee_ids = set()
    for spec in specs:
        workflow = workflows.get(spec["key"])
        task = task_by_instance.get(int(workflow.id)) if workflow else None
        todo = todo_by_key.get(spec["key"])
        assignee_id = int((task.assignee_id if task else None) or (todo.assignee_id if todo else 0) or 0)
        if assignee_id:
            assignee_ids.add(assignee_id)
    users = {}
    if assignee_ids:
        users = {int(row.id): row for row in db.scalars(select(User).where(
            User.tenant_id == tenant_id, User.id.in_(assignee_ids), User.is_deleted.is_(False),
        )).all()}

    result = {}
    for spec in specs:
        workflow = workflows.get(spec["key"])
        task = task_by_instance.get(int(workflow.id)) if workflow else None
        todo = todo_by_key.get(spec["key"])
        assignee_id = int((task.assignee_id if task else None) or (todo.assignee_id if todo else 0) or 0)
        assignee = users.get(assignee_id)
        node = (workflow.current_node if workflow else None) or (task.node_code if task else None) or ""
        due_at = (task.deadline_at if task else None) or (todo.due_at if todo else None)
        result[spec["key"]] = {
            "workflowId": str(workflow.id) if workflow else "",
            "workflowStatus": workflow.status if workflow else "",
            "currentNode": node, "currentNodeLabel": _NODE_LABELS.get(node, node),
            "handlerId": str(assignee_id) if assignee_id else "",
            "handler": (assignee.real_name if assignee else "") or "待分配",
            "dueAt": _iso(due_at),
        }
    return result


def _batch_timelines(db, specs: list[dict]) -> dict[str, list[dict]]:
    from app.models import AffairsAuditTrail

    if not specs:
        return {}
    biz_ids = {int(spec["biz_id"]) for spec in specs}
    biz_types = {_biz(spec["biz_type"]) for spec in specs}
    rows = db.scalars(select(AffairsAuditTrail).where(
        AffairsAuditTrail.tenant_id == _tid(),
        AffairsAuditTrail.biz_id.in_(biz_ids),
        AffairsAuditTrail.biz_type.in_(biz_types),
    ).order_by(AffairsAuditTrail.occurred_at, AffairsAuditTrail.id)).all()
    grouped: dict[tuple[str, int], list] = {}
    for row in rows:
        grouped.setdefault((_biz(row.biz_type), int(row.biz_id)), []).append(row)
    result = {}
    for spec in specs:
        key_rows = grouped.get((_biz(spec["biz_type"]), int(spec["biz_id"])), [])
        items = []
        created_at = spec.get("created_at")
        if created_at and (not key_rows or created_at < key_rows[0].occurred_at):
            items.append({
                "eventId": f"created-{spec['biz_type']}-{spec['biz_id']}",
                "action": "CREATED", "actionLabel": "申请创建", "operator": "学生本人",
                "role": "STUDENT", "occurredAt": _iso(created_at), "description": "申请已创建",
                "fromStatus": "", "toStatus": "", "attachments": [],
            })
        for row in key_rows:
            items.append({
                "eventId": str(row.id), "action": row.action,
                "actionLabel": _ACTION_LABELS.get(row.action, row.action),
                "operator": row.operator or "系统", "role": row.role_name or "",
                "occurredAt": _iso(row.occurred_at), "description": row.detail or "",
                "fromStatus": row.before_val or "", "toStatus": row.after_val or "", "attachments": [],
            })
        result[spec["key"]] = items
    return result


def _material_contract_from_rows(rows: list, status: str) -> dict:
    data = [{
        "attachmentId": str(row.id), "fileId": str(row.file_id) if not row.is_deleted else "",
        "fileName": row.file_name or "材料附件", "note": row.note or "",
        "version": int(row.version or 0), "uploadedAt": _iso(row.created_at),
        "active": not bool(row.is_deleted), "downloadable": not bool(row.is_deleted),
    } for row in rows]
    current = [item for item in data if item["active"]]
    history = [item for item in data if not item["active"]]
    returned = str(status or "").upper() in {"DRAFT", "RETURNED"}
    return {
        "current": current, "history": history, "currentCount": len(current),
        "historyCount": len(history), "missingItems": [], "missingItemsKnown": False,
        "supplementStatus": "PENDING_STUDENT_EDIT" if returned else "NOT_PENDING",
    }


def _batch_materials(db, specs: list[dict]) -> dict[str, dict]:
    from app.models import AffairsAttachment

    if not specs:
        return {}
    biz_ids = {int(spec["biz_id"]) for spec in specs}
    biz_types = {_biz(value) for spec in specs for value in spec["biz_types"]}
    rows = db.scalars(select(AffairsAttachment).where(
        AffairsAttachment.tenant_id == _tid(),
        AffairsAttachment.biz_id.in_(biz_ids),
        AffairsAttachment.biz_type.in_(biz_types),
    ).order_by(AffairsAttachment.created_at.desc(), AffairsAttachment.id.desc())).all()
    grouped: dict[tuple[str, int], list] = {}
    for row in rows:
        grouped.setdefault((_biz(row.biz_type), int(row.biz_id)), []).append(row)
    result = {}
    for spec in specs:
        selected = []
        for biz_type in spec["biz_types"]:
            selected.extend(grouped.get((_biz(biz_type), int(spec["biz_id"])), []))
        selected.sort(key=lambda row: (row.created_at, row.id), reverse=True)
        result[spec["key"]] = _material_contract_from_rows(selected, spec["status"])
    return result

def _merge_materials(*contracts: dict) -> dict:
    current, history = [], []
    for contract in contracts:
        current.extend(contract.get("current") or [])
        history.extend(contract.get("history") or [])
    returned = any((contract.get("supplementStatus") == "PENDING_STUDENT_EDIT") for contract in contracts)
    return {
        "current": current, "history": history,
        "currentCount": len(current), "historyCount": len(history),
        "missingItems": [], "missingItemsKnown": False,
        "supplementStatus": "PENDING_STUDENT_EDIT" if returned else "NOT_PENDING",
    }


def _application(*, biz_type: str, record_id: Any, no: str, title: str, status: str,
                 status_label: str, submitted_at, version: int, actions: Iterable[str],
                 workflow: dict, timeline: list[dict], materials: dict,
                 last_opinion: str = "", department: str = "学工中心") -> dict:
    bt = _biz(biz_type)
    rid = str(record_id)
    allowed = _safe_actions(actions)
    group = _status_group(status, allowed)
    action_key = _ACTION_KEY_BY_BIZ.get(bt, "AFFAIRS_APPLICATIONS")
    next_action = _next_action(status, allowed, workflow.get("handler") or "")
    return {
        "applicationId": f"{bt.lower()}-{rid}", "bizType": bt, "recordId": rid,
        "applicationNo": no, "title": title, "status": status,
        "statusLabel": status_label or status, "statusGroup": group,
        "submittedAt": _iso(submitted_at), "department": department,
        "currentNode": workflow.get("currentNode") or "",
        "currentNodeLabel": workflow.get("currentNodeLabel") or "",
        "handlerId": workflow.get("handlerId") or "", "handler": workflow.get("handler") or "待分配",
        "dueAt": workflow.get("dueAt"), "lastOpinion": last_opinion or "",
        "allowedActions": allowed, "nextAction": next_action, "version": int(version or 0),
        "actionKey": action_key, "actionParams": {"bizType": bt, "recordId": rid},
        "timeline": timeline, "materials": materials,
        "id": f"{bt.lower()}-{rid}", "no": no, "name": title, "group": group,
        "statusText": status_label or status, "applyTime": _iso(submitted_at),
        "dept": department, "hasResult": group != "processing", "sourceType": bt,
    }


def _normalize_legacy(item: dict) -> dict:
    bt = _biz(item.get("sourceType") or "WORKORDER")
    rid = str(item.get("recordId") or str(item.get("id") or "").split("-")[-1])
    status = str(item.get("status") or "")
    group = item.get("group") or _status_group(status)
    action_key = _ACTION_KEY_BY_BIZ.get(bt, "AFFAIRS_APPLICATIONS")
    return {
        **item,
        "applicationId": item.get("applicationId") or f"{bt.lower()}-{rid}",
        "bizType": bt, "recordId": rid,
        "applicationNo": item.get("applicationNo") or item.get("no") or "",
        "title": item.get("title") or item.get("name") or "学工申请",
        "statusLabel": item.get("statusLabel") or item.get("statusText") or status,
        "statusGroup": group, "submittedAt": item.get("submittedAt") or item.get("applyTime"),
        "department": item.get("department") or item.get("dept") or "学工中心",
        "currentNode": item.get("currentNode") or "", "currentNodeLabel": item.get("currentNodeLabel") or "",
        "handlerId": item.get("handlerId") or "", "handler": item.get("handler") or "待分配",
        "dueAt": item.get("dueAt"), "allowedActions": _safe_actions(item.get("allowedActions")),
        "nextAction": item.get("nextAction") or _next_action(status, [], item.get("handler") or ""),
        "version": int(item.get("version") or 0), "actionKey": action_key,
        "actionParams": {"bizType": bt, "recordId": rid},
        "timeline": item.get("timeline") or [],
        "materials": item.get("materials") or {
            "current": [], "history": [], "currentCount": 0, "historyCount": 0,
            "missingItems": [], "missingItemsKnown": False, "supplementStatus": "NOT_PENDING",
        },
    }


def _build_my_applications(user: dict, original) -> dict:
    from app.models import (AffairsCreditAppeal, AidApply, CsLeave, DisciplineAppeal,
                            DisciplineCase, DormTransfer, FundingApplication)
    from app.services import mobile_affairs_service as aff
    from app.services.mobile_student_service import _require_student, resolve_student

    _require_student(user)
    legacy = original(user) or {}
    applications: list[dict] = []
    descriptors: list[dict] = []

    def queue(*, workflow_biz_type: str, workflow_id: int | None, timeline_biz_type: str,
              timeline_biz_id: int, created_at, material_refs: list[tuple[tuple[str, ...], int, str]],
              application: dict) -> None:
        key = f"application-{len(descriptors)}"
        material_specs = []
        for index, (biz_types, biz_id, status) in enumerate(material_refs):
            material_specs.append({
                "key": f"{key}-material-{index}", "biz_types": biz_types,
                "biz_id": int(biz_id), "status": status,
            })
        descriptors.append({
            "key": key,
            "workflow": {"key": key, "biz_type": workflow_biz_type,
                         "biz_id": int(application["record_id"]), "workflow_id": workflow_id},
            "timeline": {"key": key, "biz_type": timeline_biz_type,
                         "biz_id": int(timeline_biz_id), "created_at": created_at},
            "materials": material_specs, "application": application,
        })

    with session() as db:
        student = resolve_student(db, user)
        if not student:
            return {"hasData": False, "tabs": legacy.get("tabs") or [], "applications": []}
        sid = int(student.id)

        leave_view = aff.leave_my(user)
        leave_ids = {int(x["leaveId"]) for x in leave_view.get("items", [])
                     if str(x.get("leaveId") or "").isdigit()}
        leaves = {int(x.id): x for x in db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(), CsLeave.id.in_(leave_ids or {-1}),
            CsLeave.is_deleted.is_(False))).all()}
        for item in leave_view.get("items", []):
            row = leaves.get(int(item["leaveId"]))
            if not row:
                continue
            status = item.get("status") or row.affairs_status or row.status
            queue(
                workflow_biz_type="LEAVE", workflow_id=getattr(row, "workflow_instance_id", None),
                timeline_biz_type="LEAVE", timeline_biz_id=row.id, created_at=row.created_at,
                material_refs=[(("LEAVE",), row.id, status)],
                application=dict(
                    biz_type="LEAVE", record_id=row.id, no=row.code or f"LV{row.id}",
                    title=f"学生请假（{item.get('leaveTypeLabel') or item.get('leaveType') or ''}）",
                    status=status, status_label=item.get("statusLabel") or status,
                    submitted_at=row.apply_time or row.created_at, version=item.get("version") or row.version,
                    actions=item.get("allowedActions") or [], last_opinion=item.get("returnReason") or "",
                    department="学工处",
                ),
            )

        aid_view = aff.aid_my(user)
        aid_ids = {int(x["applyId"]) for x in aid_view.get("items", [])
                   if str(x.get("applyId") or "").isdigit()}
        aids = {int(x.id): x for x in db.scalars(select(AidApply).where(
            AidApply.tenant_id == _tid(), AidApply.id.in_(aid_ids or {-1}),
            AidApply.is_deleted.is_(False))).all()}
        for item in aid_view.get("items", []):
            row = aids.get(int(item["applyId"]))
            if not row:
                continue
            status = item.get("status") or row.status
            queue(
                workflow_biz_type="AID", workflow_id=row.workflow_instance_id,
                timeline_biz_type="AID", timeline_biz_id=row.id, created_at=row.created_at,
                material_refs=[(("AID",), row.id, status)],
                application=dict(
                    biz_type="AID", record_id=row.id, no=f"AID{row.id}",
                    title="家庭经济困难认定", status=status,
                    status_label=item.get("statusLabel") or status, submitted_at=row.created_at,
                    version=item.get("version") or row.version, actions=item.get("allowedActions") or [],
                    last_opinion=item.get("returnReason") or "", department="资助中心",
                ),
            )

        funding_view = aff.funding_my(user)
        funding_ids = {int(x["applicationId"]) for x in funding_view.get("items", [])
                       if str(x.get("applicationId") or "").isdigit()}
        fundings = {int(x.id): x for x in db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.id.in_(funding_ids or {-1}),
            FundingApplication.is_deleted.is_(False))).all()}
        for item in funding_view.get("items", []):
            row = fundings.get(int(item["applicationId"]))
            if not row:
                continue
            status = item.get("status") or row.status
            queue(
                workflow_biz_type="FUNDING", workflow_id=row.workflow_instance_id,
                timeline_biz_type="FUNDING", timeline_biz_id=row.id, created_at=row.created_at,
                material_refs=[(("FUNDING",), row.id, status)],
                application=dict(
                    biz_type="FUNDING", record_id=row.id, no=f"FUND{row.id}", title="奖助申请",
                    status=status, status_label=item.get("statusLabel") or status,
                    submitted_at=row.created_at, version=item.get("version") or row.version,
                    actions=item.get("allowedActions") or [], last_opinion=item.get("returnReason") or "",
                    department="资助中心",
                ),
            )

        cases = db.scalars(select(DisciplineCase).where(
            DisciplineCase.tenant_id == _tid(), DisciplineCase.student_id == sid,
            DisciplineCase.status == "EFFECTIVE", DisciplineCase.is_deleted.is_(False))).all()
        appeals = db.scalars(select(DisciplineAppeal).where(
            DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.student_id == sid,
            DisciplineAppeal.is_deleted.is_(False)).order_by(DisciplineAppeal.id.desc())).all()
        latest = {}
        for appeal in appeals:
            latest.setdefault(int(appeal.case_id), appeal)
        disc_labels = {"WARNING": "警告", "SERIOUS_WARNING": "严重警告", "DEMERIT": "记过",
                       "PROBATION": "留校察看", "EXPEL": "开除学籍"}
        for case in cases:
            appeal = latest.get(int(case.id))
            record = appeal or case
            status = appeal.status if appeal else case.status
            actions = [] if appeal else ["SUBMIT_APPEAL"]
            material_refs = [(("DISCIPLINE",), case.id, case.status)]
            if appeal:
                material_refs.append((("DISCIPLINE_APPEAL",), appeal.id, status))
            queue(
                workflow_biz_type="DISCIPLINE_APPEAL" if appeal else "DISCIPLINE",
                workflow_id=getattr(record, "workflow_instance_id", None),
                timeline_biz_type="DISCIPLINE", timeline_biz_id=case.id, created_at=case.created_at,
                material_refs=material_refs,
                application=dict(
                    biz_type="DISCIPLINE_APPEAL", record_id=record.id,
                    no=case.doc_no or f"DISC{case.id}",
                    title=f"处分申诉（{disc_labels.get(case.disc_type, case.disc_type)}）",
                    status=status, status_label=status, submitted_at=record.created_at,
                    version=record.version, actions=actions,
                    last_opinion=(appeal.review_opinion if appeal else case.return_reason) or "",
                    department="学工处",
                ),
            )

        transfers = db.scalars(select(DormTransfer).where(
            DormTransfer.tenant_id == _tid(), DormTransfer.student_id == sid,
            DormTransfer.is_deleted.is_(False)).order_by(DormTransfer.id.desc())).all()
        dorm_labels = {"SUBMITTED": "已提交", "COUNSELOR_REVIEW": "辅导员审批",
                       "DORM_MANAGER_REVIEW": "宿管审批", "APPROVED": "已通过",
                       "REJECTED": "已驳回", "RETURNED": "已退回", "CANCELLED": "已取消",
                       "EXECUTED": "已完成调宿"}
        for row in transfers:
            actions = ["EDIT_RETURNED", "RESUBMIT"] if row.status == "RETURNED" else []
            queue(
                workflow_biz_type="DORM_TRANSFER", workflow_id=row.workflow_instance_id,
                timeline_biz_type="DORM_TRANSFER", timeline_biz_id=row.id, created_at=row.created_at,
                material_refs=[(("DORM", "DORM_TRANSFER"), row.id, row.status)],
                application=dict(
                    biz_type="DORM_TRANSFER", record_id=row.id, no=f"DORM{row.id}", title="调宿申请",
                    status=row.status, status_label=dorm_labels.get(row.status, row.status),
                    submitted_at=row.created_at, version=row.version, actions=actions,
                    last_opinion=row.return_reason or "", department="宿舍管理",
                ),
            )

        credits = db.scalars(select(AffairsCreditAppeal).where(
            AffairsCreditAppeal.tenant_id == _tid(), AffairsCreditAppeal.student_id == sid,
            AffairsCreditAppeal.is_deleted.is_(False)).order_by(AffairsCreditAppeal.id.desc())).all()
        credit_labels = {"SUBMITTED": "已提交", "APPROVED": "已通过", "REJECTED": "已驳回"}
        for row in credits:
            queue(
                workflow_biz_type="SECOND_CLASS_APPEAL", workflow_id=None,
                timeline_biz_type="CREDIT_APPEAL", timeline_biz_id=row.id, created_at=row.created_at,
                material_refs=[(("CREDIT_APPEAL", "SECOND_CLASS_APPEAL"), row.id, row.status)],
                application=dict(
                    biz_type="CREDIT_APPEAL", record_id=row.id, no=f"SC{row.id}",
                    title="第二课堂积分申诉", status=row.status,
                    status_label=credit_labels.get(row.status, row.status), submitted_at=row.created_at,
                    version=row.version, actions=[], last_opinion=row.review_opinion or "",
                    department="第二课堂中心",
                ),
            )

        workflow_specs = [descriptor["workflow"] for descriptor in descriptors]
        timeline_specs = [descriptor["timeline"] for descriptor in descriptors]
        material_specs = [spec for descriptor in descriptors for spec in descriptor["materials"]]
        workflow_map = _batch_workflow_contexts(db, workflow_specs)
        timeline_map = _batch_timelines(db, timeline_specs)
        material_map = _batch_materials(db, material_specs)
        for descriptor in descriptors:
            contracts = [material_map.get(spec["key"], _material_contract_from_rows([], spec["status"]))
                         for spec in descriptor["materials"]]
            materials = contracts[0] if len(contracts) == 1 else _merge_materials(*contracts)
            applications.append(_application(
                **descriptor["application"],
                workflow=workflow_map.get(descriptor["key"], _empty_workflow_context()),
                timeline=timeline_map.get(descriptor["key"], []),
                materials=materials,
            ))

    for item in legacy.get("applications") or []:
        if _biz(item.get("sourceType")) in {"LEAVE"}:
            continue
        applications.append(_normalize_legacy(item))
    applications.sort(key=lambda x: x.get("submittedAt") or "", reverse=True)
    tabs = legacy.get("tabs") or [
        {"key": "all", "label": "全部"}, {"key": "processing", "label": "处理中"},
        {"key": "done", "label": "已办结"}, {"key": "rejected", "label": "退回/驳回"},
    ]
    return {"hasData": bool(applications), "tabs": tabs, "applications": applications,
            "contractVersion": "AFFAIRS_APPLICATION_V1"}


def _patch_discipline_actions() -> None:
    from app.services import mobile_affairs_service as aff

    original = aff.discipline_my

    def discipline_my(user):
        data = original(user)
        ids = {int(x["caseId"]) for x in data.get("items", []) if str(x.get("caseId") or "").isdigit()}
        versions = {}
        if ids:
            from app.models import DisciplineCase
            with session() as db:
                versions = {int(row.id): int(row.version or 0) for row in db.scalars(select(DisciplineCase).where(
                    DisciplineCase.tenant_id == _tid(), DisciplineCase.id.in_(ids),
                    DisciplineCase.is_deleted.is_(False))).all()}
        for item in data.get("items", []):
            case_id = int(item["caseId"]) if str(item.get("caseId") or "").isdigit() else 0
            item["version"] = versions.get(case_id, 0)
            item["allowedActions"] = _safe_actions(item.get("allowedActions"))
            item["actionKey"] = "AFFAIRS_DISCIPLINE"
            item["actionParams"] = {"bizType": "DISCIPLINE", "recordId": str(case_id)}
        return data

    aff.discipline_my = discipline_my


def _patch_application_view() -> None:
    from app.services import mobile_student_service as student

    original = student.my_applications

    def my_applications(user):
        return _build_my_applications(user, original)

    student.my_applications = my_applications


def _default_action(source_biz_type: Any, source_biz_id: Any) -> tuple[str | None, dict]:
    bt = _biz(source_biz_type)
    key = _ACTION_KEY_BY_BIZ.get(bt)
    params = {"bizType": bt, "recordId": str(source_biz_id)} if key and source_biz_id is not None else {}
    return key, params


def _patch_message_producers() -> None:
    from app.services import message_event_outbox_service as outbox

    original = outbox.emit_receiver_notice

    def emit_receiver_notice(db, **kwargs):
        if kwargs.get("receiver_as", "student") == "student" and not kwargs.get("action_key"):
            key, params = _default_action(kwargs.get("source_biz_type"), kwargs.get("source_biz_id"))
            if key:
                kwargs["action_key"] = key
                kwargs["action_params"] = {**params, **(kwargs.get("action_params") or {})}
        return original(db, **kwargs)

    outbox.emit_receiver_notice = emit_receiver_notice


def _patch_message_views() -> None:
    from app.services import mobile_student_service as student

    original = student.my_messages
    original_detail = student.message_get

    def my_messages(user):
        data = original(user)
        items = [x for x in data.get("list", []) if x.get("kind") == "UNIFIED_MESSAGE"]
        ids = {int(x["messageId"]) for x in items if str(x.get("messageId") or "").isdigit()}
        if not ids:
            return data
        from app.models import UnifiedMessage
        with session() as db:
            rows = db.scalars(select(UnifiedMessage).where(
                UnifiedMessage.tenant_id == _tid(), UnifiedMessage.id.in_(ids),
                UnifiedMessage.is_deleted.is_(False))).all()
            mapping = {int(row.id): row for row in rows}
        for item in items:
            row = mapping.get(int(item["messageId"]))
            if not row:
                continue
            key = row.action_key
            params = dict(row.action_params_json or {})
            biz_type = getattr(row, "source_biz_type", None) or row.source_module
            if not key:
                key, defaults = _default_action(biz_type, row.source_biz_id)
                params = {**defaults, **params}
            item["actionKey"] = key
            item["actionParams"] = params
            item["recordId"] = str(row.source_biz_id or "")
            item["bizType"] = _biz(biz_type)
        return data

    def message_get(user, message_id):
        data = original_detail(user, message_id)
        if not data.get("actionKey"):
            key, defaults = _default_action(data.get("bizType") or data.get("module"),
                                            data.get("recordId") or data.get("messageId"))
            try:
                from app.models import UnifiedMessage
                mid = int(str(message_id).replace("msg-", ""))
                with session() as db:
                    row = db.get(UnifiedMessage, mid)
                    if row and not row.is_deleted and row.tenant_id == _tid():
                        biz_type = getattr(row, "source_biz_type", None) or row.source_module
                        key, defaults = _default_action(biz_type, row.source_biz_id)
            except (TypeError, ValueError):
                pass
            if key:
                data["actionKey"] = key
                data["actionParams"] = {**defaults, **(data.get("actionParams") or {})}
                data["recordId"] = defaults.get("recordId", "")
                data["bizType"] = defaults.get("bizType", "")
        return data

    student.my_messages = my_messages
    student.message_get = message_get


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_discipline_actions()
    _patch_application_view()
    _patch_message_producers()
    _patch_message_views()
    _INSTALLED = True
