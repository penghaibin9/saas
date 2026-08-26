"""移动端·学籍异动审批与退回重交补齐。

教师审批继续复用 ``mobile_teacher_service``；学生退回重交只恢复原 AaStatusChange / 原
workflow instance，不新建第二张异动单。补充 GET 只给本人 RETURNED 原单返回重交所需
version/reason，供真实页面携带 optimistic lock。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.services import mobile_teacher_service as tea
from app.modules.academic_affairs.services import academic_affairs_change_resubmit_meta_service as resubmit_meta
from app.modules.academic_affairs.services import academic_affairs_change_resubmit_service as resubmit

router = APIRouter(prefix="/mobile", tags=["移动端聚合"])


@router.get("/academic/status-changes/{change_id}/resubmit", summary="学籍异动·退回原单重交元数据")
def student_academic_status_change_resubmit_meta(
    change_id: str,
    user=Depends(get_current_user),
):
    return success(resubmit_meta.get_my(user, change_id))


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
