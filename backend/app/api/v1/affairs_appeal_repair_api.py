"""异议/申诉补偿队列维护接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import no_permission
from app.core.permissions import has_permission
from app.core.response import success
from app.core.security import get_current_user

router = APIRouter(tags=["学工中心·申诉补偿"])

_REQUIRED = (
    "studentAffairs.aid.approve",
    "studentAffairs.funding.publicity.manage",
    "studentAffairs.discipline.appeal.review",
    "studentAffairs.activity.confirm",
)


def _require_comprehensive_manager(user: dict) -> None:
    if not all(has_permission(user, code) for code in _REQUIRED):
        raise no_permission("仅综合学工管理员可执行申诉待办补偿")


@router.post("/mobile/teacher/affairs/appeals/repair", summary="重试异议/申诉待办与结果消息补偿")
def repair_appeals(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    _require_comprehensive_manager(user)
    from app.services.affairs_appeal_repair_service import repair_pending
    return success(repair_pending(limit), message="补偿扫描已完成")
