"""教材征订取消与退领异常关闭入口。

主教材router保持不改大文件；本小router只补P0闭环动作，所有事实仍写既有教材表和统一审计。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_textbook_service as textbook_svc

router = APIRouter(prefix="/academic-affairs/textbooks", tags=["教务中心-教材异常关闭"])


class TextbookReasonBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


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
