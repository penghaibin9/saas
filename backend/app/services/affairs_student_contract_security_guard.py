"""学生统一合同最终安全门。

- 学生时间线不透出内部审计 detail/before/after 原文；
- 没有显式可见性列的附件仅返回学生本人上传的元数据；
- 处分申请始终以案件 ID 为稳定标识；
- 调宿退回没有真实编辑重提接口时不返回假动作；
- 历史消息动作键统一转换为四端标准键。
"""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.services.db_service import _iso, _tid, session

_INSTALLED = False

_SAFE_ACTION_LABELS = {
    "CREATED": "申请创建",
    "APPLY": "提交申请",
    "SUBMIT": "提交申请",
    "STUDENT_EDIT_RETURNED": "学生修改退回内容",
    "STUDENT_RESUBMIT": "学生重新提交",
    "APPROVE": "审批通过",
    "REJECT": "审批驳回",
    "RETURN": "退回修改",
    "CLOSE": "办理关闭",
}
_CANONICAL_MESSAGE_ACTIONS = {
    "AFFAIRS_LEAVE", "AFFAIRS_AID", "AFFAIRS_FUNDING", "AFFAIRS_DISCIPLINE",
    "AFFAIRS_DORM", "AFFAIRS_ACTIVITY", "AFFAIRS_APPLICATIONS",
}
_LEGACY_MESSAGE_ACTIONS = {
    "student.leave.detail": "AFFAIRS_LEAVE",
    "student.affairs.leave": "AFFAIRS_LEAVE",
    "student.affairs.aid": "AFFAIRS_AID",
    "student.affairs.funding": "AFFAIRS_FUNDING",
    "student.affairs.discipline": "AFFAIRS_DISCIPLINE",
    "student.affairs.dorm": "AFFAIRS_DORM",
    "student.affairs.activity": "AFFAIRS_ACTIVITY",
}


def _safe_status_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 80 or "=" in text:
        return ""
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_- >")
    return text if all(ch in allowed for ch in text) else ""


def _secure_timeline(db, *, biz_type: str, biz_id: int, created_at=None) -> list[dict]:
    from app.models import AffairsAuditTrail

    rows = db.scalars(select(AffairsAuditTrail).where(
        AffairsAuditTrail.tenant_id == _tid(),
        AffairsAuditTrail.biz_type == biz_type,
        AffairsAuditTrail.biz_id == int(biz_id),
    ).order_by(AffairsAuditTrail.occurred_at, AffairsAuditTrail.id)).all()
    items: list[dict] = []
    if created_at and (not rows or created_at < rows[0].occurred_at):
        items.append({
            "eventId": f"created-{biz_type}-{biz_id}",
            "action": "CREATED", "actionLabel": "申请创建",
            "operator": "学生本人", "role": "STUDENT",
            "occurredAt": _iso(created_at), "description": "申请已创建",
            "fromStatus": "", "toStatus": "", "attachments": [],
        })
    for row in rows:
        label = _SAFE_ACTION_LABELS.get(row.action, "办理状态已更新")
        items.append({
            "eventId": str(row.id), "action": row.action, "actionLabel": label,
            "operator": row.operator or "系统", "role": row.role_name or "",
            "occurredAt": _iso(row.occurred_at), "description": label,
            "fromStatus": _safe_status_token(row.before_val),
            "toStatus": _safe_status_token(row.after_val), "attachments": [],
        })
    return items


def _owner_ids(db) -> set[int]:
    user = get_current_user_ctx() or {}
    ids: set[int] = set()
    from app.services.message_identity import resolve_message_user_id
    uid = resolve_message_user_id(user)
    if uid:
        ids.add(int(uid))
    raw_sid = str(user.get("studentId") or "")
    if raw_sid.isdigit():
        ids.add(int(raw_sid))
    try:
        from app.services.mobile_student_service import resolve_student
        student = resolve_student(db, user)
        if student:
            ids.add(int(student.id))
    except Exception:
        # 无法确认本人时 fail-closed，不为材料列表放宽。
        pass
    return ids


def _secure_materials(db, *, biz_types: Iterable[str], biz_id: int, status: str) -> dict:
    from app.models import AffairsAttachment

    owner_ids = _owner_ids(db)
    variants = {str(x or "").strip().upper().replace("-", "_") for x in biz_types if x}
    rows = []
    if owner_ids:
        rows = db.scalars(select(AffairsAttachment).where(
            AffairsAttachment.tenant_id == _tid(),
            AffairsAttachment.biz_type.in_(variants or {"__NONE__"}),
            AffairsAttachment.biz_id == int(biz_id),
            AffairsAttachment.created_by.in_(owner_ids),
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
        "visibility": "OWNER_ONLY",
    } for row in rows]
    current = [item for item in data if item["active"]]
    history = [item for item in data if not item["active"]]
    returned = str(status or "").upper() in {"DRAFT", "RETURNED"}
    return {
        "current": current, "history": history,
        "currentCount": len(current), "historyCount": len(history),
        "missingItems": [], "missingItemsKnown": False,
        "supplementStatus": "PENDING_STUDENT_EDIT" if returned else "NOT_PENDING",
    }


def _secure_application_view(original):
    def my_applications(user):
        data = original(user)
        apps = data.get("applications") or []
        appeal_case_map: dict[int, int] = {}
        # 只有已生成申诉记录的条目才把 recordId 当作 appealId 查询；
        # 尚未申诉的 EFFECTIVE 案件虽然数字可能与另一申诉同号，也绝不能被错误映射。
        ids = {
            int(item.get("recordId"))
            for item in apps
            if item.get("bizType") == "DISCIPLINE_APPEAL"
            and str(item.get("recordId") or "").isdigit()
            and "SUBMIT_APPEAL" not in (item.get("allowedActions") or [])
            and item.get("status") != "EFFECTIVE"
        }
        if ids:
            from app.models import DisciplineAppeal
            from app.services.mobile_student_service import resolve_student
            with session() as db:
                student = resolve_student(db, user)
                if student:
                    rows = db.scalars(select(DisciplineAppeal).where(
                        DisciplineAppeal.tenant_id == _tid(),
                        DisciplineAppeal.id.in_(ids),
                        DisciplineAppeal.student_id == int(student.id),
                        DisciplineAppeal.is_deleted.is_(False),
                    )).all()
                    appeal_case_map = {int(row.id): int(row.case_id) for row in rows}
        for item in apps:
            if item.get("bizType") == "DISCIPLINE_APPEAL":
                old_id = int(item["recordId"]) if str(item.get("recordId") or "").isdigit() else 0
                case_id = appeal_case_map.get(old_id, old_id)
                item["bizType"] = "DISCIPLINE"
                item["sourceType"] = "DISCIPLINE"
                item["recordId"] = str(case_id)
                item["applicationId"] = f"discipline-{case_id}"
                item["id"] = f"discipline-{case_id}"
                item["actionKey"] = "AFFAIRS_DISCIPLINE"
                item["actionParams"] = {"bizType": "DISCIPLINE", "recordId": str(case_id)}
            if item.get("bizType") == "DORM_TRANSFER" and item.get("status") == "RETURNED":
                item["allowedActions"] = []
                item["nextAction"] = {
                    "key": "WAIT", "label": "请联系辅导员或宿管处理退回事项", "actor": "STAFF",
                }
        return data
    return my_applications


def _canonical_message_action(item: dict, contract) -> None:
    current = str(item.get("actionKey") or "").strip()
    if current in _CANONICAL_MESSAGE_ACTIONS:
        return
    canonical = _LEGACY_MESSAGE_ACTIONS.get(current)
    biz_type = contract._biz(item.get("bizType") or "")
    if not canonical:
        canonical = contract._ACTION_KEY_BY_BIZ.get(biz_type)
    if not canonical:
        return
    record_id = str(item.get("recordId") or (item.get("actionParams") or {}).get("recordId") or "")
    params = dict(item.get("actionParams") or {})
    params.setdefault("bizType", biz_type)
    if record_id:
        params.setdefault("recordId", record_id)
    item["actionKey"] = canonical
    item["actionParams"] = params


def _secure_message_views(student, contract) -> None:
    original_list = student.my_messages
    original_detail = student.message_get

    def my_messages(user):
        data = original_list(user)
        for item in data.get("list") or []:
            if item.get("kind") == "UNIFIED_MESSAGE":
                _canonical_message_action(item, contract)
        return data

    def message_get(user, message_id):
        data = original_detail(user, message_id)
        _canonical_message_action(data, contract)
        return data

    student.my_messages = my_messages
    student.message_get = message_get


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_student_contract_service as contract
    from app.services import mobile_student_service as student

    contract._timeline = _secure_timeline
    contract._materials = _secure_materials
    student.my_applications = _secure_application_view(student.my_applications)
    _secure_message_views(student, contract)
    _INSTALLED = True
