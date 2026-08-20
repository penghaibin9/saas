"""移动教师端·学籍异动审批路由补齐。

业务逻辑、节点权限、数据范围与审计全部复用 ``mobile_teacher_service``；本模块只补齐
小程序 realApi 已正式消费、但历史 mobile 聚合 Router 漏注册的两个 HTTP 合同。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.services import mobile_teacher_service as tea

router = APIRouter(prefix="/mobile", tags=["移动端聚合"])


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
