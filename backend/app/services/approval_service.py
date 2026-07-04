"""审批任务服务（阶段12）：DB_ENABLED=false 内存 mock；true 预留 t_workflow_task 查询（TODO P3）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.core.pagination import page_slice

_now = lambda: datetime.now().isoformat(timespec="seconds")  # noqa: E731

_TASKS: list[dict] = [
    {"taskId": "at-1001", "instanceId": "wi-2001", "tenantId": "1000000000000000001",
     "title": "张一鸣 · 学籍信息变更", "sourceModule": "student", "sourceBizType": "PROFILE_CORRECTION",
     "applicantName": "张一鸣", "nodeCode": "COUNSELOR_REVIEW", "nodeName": "辅导员审核",
     "status": "PENDING", "submittedAt": "2026-07-01 09:32", "stayHours": 26, "urgency": "NEAR_DEADLINE"},
    {"taskId": "at-1002", "instanceId": "wi-2002", "tenantId": "1000000000000000001",
     "title": "李雨桐 · 实习单位变更", "sourceModule": "intern", "sourceBizType": "COMPANY_CHANGE",
     "applicantName": "李雨桐", "nodeCode": "MENTOR_REVIEW", "nodeName": "指导教师审核",
     "status": "PENDING", "submittedAt": "2026-06-30 14:20", "stayHours": 45, "urgency": "OVERDUE"},
    {"taskId": "at-1003", "instanceId": "wi-2003", "tenantId": "1000000000000000001",
     "title": "陈浩宇 · 就业材料核验", "sourceModule": "employment", "sourceBizType": "MATERIAL_VERIFY",
     "applicantName": "陈浩宇", "nodeCode": "EMPLOYMENT_VERIFY", "nodeName": "就业老师核验",
     "status": "PENDING", "submittedAt": "2026-07-04 08:10", "stayHours": 1, "urgency": "NORMAL"},
]
_PROCESSED: list[dict] = []
_CC: list[dict] = [
    {"taskId": "cc-1", "title": "王晨 · 学业预警处理进展", "status": "CC", "createdAt": "2026-07-02 15:20"},
]


def _visible(rows):
    tid = current_tenant_id() or "1000000000000000001"
    return [r for r in rows if r.get("tenantId", tid) == tid]


def list_tasks(page: int, page_size: int, status: Optional[str] = None) -> tuple[list[dict], int]:
    # TODO(P3)：DB_ENABLED=true 查 t_workflow_task（assignee_id=当前用户 + tenant_id + PENDING）
    rows = [r for r in _visible(_TASKS) if r["status"] == "PENDING"]
    if status:
        rows = [r for r in rows if r["status"] == status]
    return page_slice(rows, page, page_size), len(rows)


def get_task(task_id: str) -> dict:
    row = next((r for r in _visible(_TASKS) if r["taskId"] == task_id), None)
    if not row:
        raise not_found("审批任务不存在")
    return {**row, "diff": [{"field": "联系电话", "oldMasked": "138****5678", "newMasked": "137****2266"}],
            "history": [{"action": "SUBMIT", "by": row["applicantName"], "at": row["submittedAt"]}]}


def _act(task_id: str, action: str, reason: str | None = None, target: str | None = None) -> dict:
    row = next((r for r in _visible(_TASKS) if r["taskId"] == task_id), None)
    if not row:
        raise not_found("审批任务不存在")
    if row["status"] != "PENDING":
        raise AppException("APPROVAL_VERSION_CONFLICT", "任务已被处理，请刷新")
    row["status"] = action
    row["actedAt"] = _now()
    if reason:
        row["actionReason"] = reason
    if target:
        row["transferTo"] = target
    _PROCESSED.append(row)
    return {"taskId": task_id, "status": action, "actedAt": row["actedAt"],
            "instanceStatus": "RUNNING" if action == "TRANSFERRED" else ("APPROVED" if action == "APPROVED" else "REJECTED")}


def approve(task_id: str, comment: str | None) -> dict:
    return _act(task_id, "APPROVED", comment)


def reject(task_id: str, reason: str) -> dict:
    return _act(task_id, "REJECTED", reason)


def transfer(task_id: str, target_user_id: str, comment: str | None) -> dict:
    return _act(task_id, "TRANSFERRED", comment, target_user_id)


def list_processed(page: int, page_size: int) -> tuple[list[dict], int]:
    return page_slice(_PROCESSED, page, page_size), len(_PROCESSED)


def list_cc(page: int, page_size: int) -> tuple[list[dict], int]:
    return page_slice(_CC, page, page_size), len(_CC)
