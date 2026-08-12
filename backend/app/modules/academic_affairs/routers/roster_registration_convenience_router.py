"""D2-U 学籍名册/注册便利性 Router。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import roster_registration_convenience_service as convenience


router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])


class BulkRegistrationPreviewBody(BaseModel):
    studentIds: list[int] = Field(min_length=1, max_length=100)


class BulkRegistrationConfirmBody(BaseModel):
    previewToken: str = Field(min_length=20, max_length=8192)


@router.get("/registration-batches/{batchId}/registration-candidates", summary="注册候选名单·人类可读组织与资格解释")
def registration_candidates(
    batchId: int = Path(...),
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    user=Depends(require_permission("academicAffairs.registration.view")),
):
    items, total = convenience.list_registration_candidates(
        batchId, user, status=status, keyword=keyword, page=page, page_size=pageSize
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/bulk-register-preview", summary="批量注册·预览（零写入）")
def bulk_register_preview(
    body: BulkRegistrationPreviewBody,
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.registration.manage")),
):
    return success(convenience.bulk_register_preview(batchId, user, body.studentIds))


@router.post("/registration-batches/{batchId}/bulk-register", summary="批量注册·确认（必须携带有效预览凭证）")
def bulk_register(
    body: BulkRegistrationConfirmBody,
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.registration.manage")),
):
    return success(convenience.bulk_register_confirm(batchId, user, body.previewToken))
