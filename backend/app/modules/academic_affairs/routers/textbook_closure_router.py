"""教材征订、发放与费用P0闭环入口。

主教材router保持不改大文件；本小router补：当前学期审核候选、发放工作台、未到货征订取消、教材退领。
所有写事实仍进入教材最终facade和统一审计。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_textbook_service as textbook_svc
from app.modules.academic_affairs.services import academic_affairs_textbook_workbench_service as workbench_svc

router = APIRouter(prefix="/academic-affairs/textbooks", tags=["教务中心-教材P0闭环"])


class TextbookReasonBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


@router.get("/review-candidates", summary="当前学期待审核教材选用候选")
def review_candidates(
    termId: int = Query(...),
    user=Depends(require_permission("academicAffairs.textbook.review.manage")),
):
    return success(workbench_svc.list_review_candidates(user, termId))


@router.get("/distribution-batches", summary="教材发放工作台批次列表")
def distribution_batches(
    termId: int | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
    user=Depends(require_permission("academicAffairs.textbook.distribution.manage")),
):
    items, total = workbench_svc.list_distribution_batches(user, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/order-batches/{batchId}/cancel", summary="取消未到货征订批次并恢复来源选用")
def cancel_order_batch(
    body: TextbookReasonBody,
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.textbook.order.manage")),
):
    return success(
        textbook_svc.cancel_order_batch(user, batchId, body.reason),
        message="征订批次已取消",
    )


@router.post("/distribution-records/{recordId}/return", summary="教材退领（已有实收时阻断并要求退款闭环）")
def return_distribution(
    body: TextbookReasonBody,
    recordId: int = Path(...),
    user=Depends(require_permission("academicAffairs.textbook.distribution.manage")),
):
    return success(
        textbook_svc.return_distribution(user, recordId, body.reason),
        message="教材已退领",
    )
