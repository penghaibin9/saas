"""移动端·学籍异动审批与退回重交补齐。

教师审批继续复用 ``mobile_teacher_service``；学生退回重交只恢复原 AaStatusChange / 原
workflow instance，不新建第二张异动单。两类补充路由都挂在既有 /mobile 聚合边界。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.services import mobile_teacher_service as tea
from app.modules.academic_affairs.services import academic_affairs_change_resubmit_service as resubmit

router = APIRouter(prefix="/mobile", tags=["移动端聚合"])


@router.post("/academic/status-changes/{change_id}/resubmit", summary="学籍异动·退回后修改重交原单")
def student_academic_status_change_resubmit(
    change_id: str,
    body: dict = Body(default={}),
    user=Depends(get_current_user),
):
    return success(resubmit.resubmit_my(user, change_id, body or {}), message="已重交")


@router.get("/teacher/academic/status-changes/pending", summary="学籍异动·待我审批")
def teacher_academic_status_change_pending(user=Depends(get_current_user)):
    return success(tea.affairs_academic_status_change_pending(user))


@router.post("/teacher/academic/status-changes/{change_id}/review", summary="学籍异动·审批")
def teacher_academic_status_change_review(
    change_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(
        tea.affairs_academic_status_change_review(
            user,
            change_id,
            str((body or {}).get("action") or "").upper(),
            (body or {}).get("reason"),
        ),
        message="已处理",
    )
