"""审批任务服务：DB 模式按 assignee 收敛；mock 仅开发演示。"""
from __future__ import annotations

from datetime import datetime
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


def list_tasks(page: int, page_size: int, status: Optional[str] = None,
               user: dict | None = None) -> tuple[list[dict], int]:
    if db_enabled():
        from app.services import db_service
        return db_service.list_tasks(page, page_size, status, user=user)
    rows = [r for r in _visible(_TASKS, user) if r["status"] == "PENDING"]
    if status:
        rows = [r for r in rows if r["status"] == status]
    return page_slice(rows, page, page_size), len(rows)


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
    return {"taskId": task_id, "status": action, "actedAt": row["actedAt"],
            "instanceStatus": "RUNNING" if action == "TRANSFERRED" else (
                "APPROVED" if action == "APPROVED" else "REJECTED")}


def approve(task_id: str, comment: str | None, user: dict | None = None,
            version: int | None = None) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.act_task(task_id, "APPROVED", comment, user=user, version=version)
    return _act(task_id, "APPROVED", comment, user=user, version=version)


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


def list_processed(page: int, page_size: int, user: dict | None = None) -> tuple[list[dict], int]:
    if db_enabled():
        from app.services import db_service
        return db_service.list_processed(page, page_size, user=user)
    return page_slice(_visible(_PROCESSED, user), page, page_size), len(_visible(_PROCESSED, user))


def list_cc(page: int, page_size: int) -> tuple[list[dict], int]:
    return page_slice(_CC, page, page_size), len(_CC)


def _check_reject_reason(reason: str) -> None:
    from app.services.platform_service import safe_rule
    try:
        tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tid = 0
    required = safe_rule(tid, "approval", "rejectReasonRequired")
    min_len = safe_rule(tid, "approval", "rejectReasonMinLength") or 0
    text = (reason or "").strip()
    if required and len(text) < int(min_len):
        raise AppException("REJECT_REASON_REQUIRED",
                           f"驳回原因不能少于 {min_len} 字（平台规则中心配置）")
