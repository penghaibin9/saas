"""包 11：处分决定版本与完整申诉复核补充 API。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.services import affairs_discipline_service as discipline

router = APIRouter(prefix="/student-affairs/discipline", tags=["学工中心·处分一致性"])


class DisciplineDecisionReviewBody(BaseModel):
    result: str = Field(..., description="UPHELD/REVISED/REVOKED")
    opinion: str = Field(..., min_length=5, max_length=1000)
    version: int = Field(..., ge=0, description="申诉当前乐观锁版本")
    revisedDiscType: Optional[str] = Field(
        None, description="REVISED 时必填：变更后的处分类型")
    revisedReason: Optional[str] = Field(
        None, max_length=1000, description="REVISED 时必填：变更后的处分事实")
    revisedDocNo: Optional[str] = Field(
        None, max_length=100, description="REVISED 时的新决定书文号")


@router.get("/cases/{case_id}/decisions", summary="处分 original/revised/revoked 决定版本链")
def decision_versions(
    case_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.discipline.view")),
):
    return success({"items": discipline.list_decision_versions(case_id, user)})


@router.post("/appeals/{appeal_id}/decision-review", summary="完整复核处分申诉并追加决定版本")
def decision_review(
    body: DisciplineDecisionReviewBody,
    appeal_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.discipline.appeal.review")),
):
    return success(
        discipline.review_appeal(appeal_id, body, user),
        message="处分申诉复核已完成",
    )
