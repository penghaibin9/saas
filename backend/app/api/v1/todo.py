"""
简化待办列表（P0 基线，GET /api/v1/todos）
────────────────────────────────────────────────────────────
与分端待办 app/api/v1/todos.py（/api/v1/{admin|student-mini|teacher-mobile}/todos，
对齐正式冻结契约）并存：本文件提供扁平化最小接口，复用此前已写好但未挂载的
services/mock_todo_service.py，便于 P0 基线联调与测试，不新增业务逻辑。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import success
from app.core.security import require_staff
from app.services import mock_todo_service as todo_svc

router = APIRouter(tags=["S7·简化-待办"])


@router.get("", summary="待办列表（简化，占位）")
def list_todos(
    status: Optional[str] = Query(default=None, description="PENDING / DONE"),
    todoType: Optional[str] = Query(default=None, description="APPROVAL/REVIEW/RISK/SUBMIT/CONFIRM"),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    user=Depends(require_staff),
):
    return success(todo_svc.list_todos(status, todoType, page, pageSize))


@router.get("/summary", summary="待办汇总（角色化计数）")
def todo_summary(user=Depends(require_staff)):
    return success(todo_svc.get_summary(user))


@router.post("/{todo_id}/done", summary="完成待办（占位：内存状态流转）")
def todo_done(todo_id: str, user=Depends(require_staff)):
    return success(todo_svc.mark_done(todo_id), message="已完成")
