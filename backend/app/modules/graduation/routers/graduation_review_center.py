"""W7.3 read-only Review Center API.

All mutations intentionally stay on the canonical Proposal/Final/Formal Review APIs.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.services import graduation_review_center_contract_service as center
from app.modules.graduation.services.graduation_batch_context import require_batch_id

router = APIRouter(prefix="/review-center", tags=["毕业设计-评阅中心"])


@router.get("/summary", summary="评阅中心摘要（服务端聚合）")
def review_center_summary(
    batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(center.summary(require_batch_id(batchId)))


@router.get("/tasks", summary="评阅中心任务队列（服务端筛选/排序/分页）")
def review_center_tasks(
    batchId: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    caseType: Optional[str] = Query(default=None),
    statusGroup: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None, max_length=100),
    reviewerOnly: bool = Query(default=False),
    sort: Optional[str] = Query(default="PRIORITY"),
    user=Depends(get_current_user),
):
    batch_id = require_batch_id(batchId)
    items, total = center.list_tasks(
        batch_id=batch_id,
        page=page,
        page_size=pageSize,
        case_type=caseType,
        status_group=statusGroup,
        keyword=keyword,
        reviewer_only=reviewerOnly,
        sort=sort,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/tasks/{case_type}/{record_id}", summary="评阅中心任务详情投影")
def review_center_detail(
    case_type: str,
    record_id: int,
    batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(center.detail(
        batch_id=require_batch_id(batchId),
        case_type=case_type,
        record_id=record_id,
    ))
