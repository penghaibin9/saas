"""岗位实习 · 成绩申诉学校端 API。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_score_appeal_service as svc

router = APIRouter(prefix="/internship/score-appeals", tags=["岗位实习-成绩申诉"])

_PUBLISH = "internship.score.publish"


@router.get("", summary="成绩申诉列表")
def list_appeals(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    batchId: Optional[str] = None,
    user=Depends(require_permission(_PUBLISH)),
):
    items, total = svc.list_appeals(
        user,
        page=page,
        page_size=pageSize,
        status=status,
        batch_id=batchId,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/{appeal_id}", summary="成绩申诉详情")
def detail(appeal_id: str, user=Depends(require_permission(_PUBLISH))):
    return success(svc.get_appeal(user, appeal_id))


@router.post("/{appeal_id}/approve", summary="受理成绩申诉并撤回原已发布成绩")
def approve(appeal_id: str, body: dict = Body(...), user=Depends(require_permission(_PUBLISH))):
    return success(svc.decide(user, appeal_id, body, approve=True), message="已受理并撤回原成绩")


@router.post("/{appeal_id}/reject", summary="驳回成绩申诉")
def reject(appeal_id: str, body: dict = Body(...), user=Depends(require_permission(_PUBLISH))):
    return success(svc.decide(user, appeal_id, body, approve=False), message="已驳回")
