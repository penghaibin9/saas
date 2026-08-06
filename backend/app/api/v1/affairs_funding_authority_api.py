"""包 10：资助批准金额双人复核补充 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field, condecimal

from app.core.permissions import require_permission
from app.core.response import success
from app.services import affairs_funding_authority_service as authority

Money = condecimal(max_digits=14, decimal_places=2, gt=0)

router = APIRouter(prefix="/student-affairs/funding", tags=["学工中心·资助金额权威化"])


class AmountAdjustmentCreate(BaseModel):
    amount: Money
    reason: str = Field(..., min_length=5, max_length=500)
    version: int = Field(..., ge=0, description="资助申请当前乐观锁版本")


class AmountAdjustmentReview(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    reason: str = Field(..., min_length=5, max_length=500)
    applicationVersion: int = Field(..., ge=0, description="资助申请当前乐观锁版本")


@router.get("/applications/{application_id}/amount-adjustments", summary="金额调整与双人复核历史")
def list_amount_adjustments(
    application_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.funding.view")),
):
    return success({"items": authority.list_adjustments(application_id, user)})


@router.post("/applications/{application_id}/amount-adjustments", summary="申请调整规则批准金额")
def create_amount_adjustment(
    body: AmountAdjustmentCreate,
    application_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.funding.approve")),
):
    return success(
        authority.request_adjustment(
            application_id, user, body.amount, body.reason, body.version,
        ),
        message="金额调整已提交，须由另一名授权人员复核",
    )


@router.post("/amount-adjustments/{adjustment_id}/review", summary="复核金额调整（申请人与复核人分离）")
def review_amount_adjustment(
    body: AmountAdjustmentReview,
    adjustment_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.funding.publicity.manage")),
):
    return success(
        authority.review_adjustment(
            adjustment_id, user, body.action, body.reason, body.applicationVersion,
        ),
        message="金额调整复核已完成",
    )
