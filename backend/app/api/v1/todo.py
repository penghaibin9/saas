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

from app.core.exceptions import AppException, not_found
from app.core.response import paginate, success
from app.core.security import require_staff
from app.db.session import db_enabled
from app.services import mock_todo_service as todo_svc
from app.services import workbench_todo_service as wb_svc

router = APIRouter(tags=["S7·简化-待办"])


@router.get("", summary="待办列表（本人可见范围）")
def list_todos(
    status: Optional[str] = Query(default=None, description="PENDING / DONE"),
    todoType: Optional[str] = Query(default=None, description="APPROVAL/REVIEW/RISK/SUBMIT/CONFIRM"),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    user=Depends(require_staff),
):
    # 真库分支按「本人指派 + 范围内池待办」收敛；db_service.list_todos 只过滤租户（全校可见），不再使用。
    if db_enabled():
        items, total = wb_svc.list_todos(user, status, todoType, page, pageSize)
        data = paginate(items, total, page, pageSize)
        data["countByType"] = wb_svc.count_todos(user)["byType"]
        return success(data)
    return success(todo_svc.list_todos(status, todoType, page, pageSize))


@router.get("/summary", summary="待办汇总（本人可见范围：待处理/逾期/临期/今日完成）")
def todo_summary(user=Depends(require_staff)):
    # 前端顶部角标消费本接口。此前走 db_service.todo_summary()：只过滤租户不分人，
    # 辅导员会看到全校待办数；且 overdue/nearDeadline 恒为 0、doneToday 实为历史全部完成数。
    if db_enabled():
        role = (user or {}).get("currentRoleCode") or "DB"
        return success({"role": role, **wb_svc.summary(user)})
    return success(todo_svc.get_summary(user))


@router.post("/{todo_id}/done", summary="完成待办（仅限本人可见范围内）")
def todo_done(todo_id: str, user=Depends(require_staff)):
    # 归属校验：此前 db_service.todo_done() 只按 id+租户更新，任意教职工可凭 ID 完成他人待办。
    if db_enabled():
        data, err = wb_svc.complete_todo(user, todo_id)
        if err == "NOT_FOUND":
            raise not_found("待办不存在")
        if err == "ALREADY_DONE":
            raise AppException("DATA_CONFLICT", "待办已完成，请勿重复操作",
                               details={"reason": "TODO_ALREADY_COMPLETED"})
        return success(data, message="已完成")
    return success(todo_svc.mark_done(todo_id), message="已完成")
