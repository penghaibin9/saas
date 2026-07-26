"""教师小程序·延期答辩导师审核（显式批次+分页）。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.graduation.services import graduation_extension_service as svc

router = APIRouter(prefix="/mobile/teacher/graduation", tags=["教师移动端-延期答辩"])


@router.get("/defense-delays/pending", summary="指导教师·本人学生延期答辩待审核")
def teacher_graduation_delay_pending(
    batchId: int = Query(..., ge=1), page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("graduationDesign.defense.view")),
):
    items, total = svc.list_delays(
        batch_id=batchId, status="PENDING_ADVISOR", page=page, page_size=pageSize,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/defense-delays/{record_id}/review", summary="指导教师审核延期答辩")
def teacher_graduation_delay_review(
    record_id: str, body: dict = Body(...),
    user=Depends(require_permission("graduationDesign.defense.view")),
):
    return success(svc.advisor_review_delay(
        record_id, body.get("action") or "", body.get("comment") or "",
    ), message="导师审核完成")
