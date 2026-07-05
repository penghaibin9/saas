"""审批任务 API（阶段12）。第一批骨架：不实现流程引擎；操作全部写审计。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import require_staff
from app.schemas.approval import ApprovalActionRequest, ApprovalRejectRequest, ApprovalTransferRequest
from app.services import approval_service as svc
from app.services import mock_audit_service as audit

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/tasks", summary="待我审批任务列表")
def list_tasks(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               user=Depends(require_staff)):
    items, total = svc.list_tasks(page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/tasks/{task_id}", summary="审批任务详情（含原值/新值 diff 与留痕）")
def get_task(task_id: str, user=Depends(require_staff)):
    return success(svc.get_task(task_id))


@router.post("/tasks/{task_id}/approve", summary="通过（写审计，返回任务与实例状态）")
def approve(task_id: str, body: ApprovalActionRequest, user=Depends(require_staff)):
    result = svc.approve(task_id, body.comment)
    audit.record("审批通过", method="POST", path=f"/api/v1/approvals/tasks/{task_id}/approve",
                 status_code=200, target_type="approval", target_id=task_id)
    return success(result, message="已通过")


@router.post("/tasks/{task_id}/reject", summary="驳回（reason 必填 ≥5 字，写审计）")
def reject(task_id: str, body: ApprovalRejectRequest, user=Depends(require_staff)):
    result = svc.reject(task_id, body.reason)
    audit.record("审批驳回", method="POST", path=f"/api/v1/approvals/tasks/{task_id}/reject",
                 status_code=200, target_type="approval", target_id=task_id)
    return success(result, message="已驳回")


@router.post("/tasks/{task_id}/transfer", summary="转办（写审计）")
def transfer(task_id: str, body: ApprovalTransferRequest, user=Depends(require_staff)):
    result = svc.transfer(task_id, body.targetUserId, body.comment)
    audit.record("审批转办", method="POST", path=f"/api/v1/approvals/tasks/{task_id}/transfer",
                 status_code=200, target_type="approval", target_id=task_id)
    return success(result, message="已转办")


@router.get("/processed", summary="已办列表")
def processed(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              user=Depends(require_staff)):
    items, total = svc.list_processed(page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/cc", summary="抄送我的")
def cc(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
       user=Depends(require_staff)):
    items, total = svc.list_cc(page, pageSize)
    return success(paginate(items, total, page, pageSize))
