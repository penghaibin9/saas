"""Stage C3 immutable archive correction API.

ARCHIVED remains permanent. These endpoints never reopen a term: they create/list a
PostArchiveCorrectionCase, let a different second operator approve it, append Manifest
V2+, and expose manifest verification. First production scope is intentionally limited
to GRADE/GRADUATION by the service layer.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_service

router = APIRouter(prefix="/academic-affairs/archive", tags=["教务归档-归档后纠错"])


class PostArchiveCorrectionCreateBody(BaseModel):
    businessType: str = Field(..., min_length=4, max_length=32, description="GRADE/GRADUATION")
    targetRef: str = Field(..., min_length=1, max_length=200)
    reason: str = Field(..., min_length=5, max_length=500)
    correction: dict[str, Any]
    evidenceManifest: dict[str, Any]
    riskLevel: str = Field(default="HIGH", min_length=3, max_length=20)


@router.get("/batches/{batch_id}/manifest/verify", summary="验证不可变归档 Manifest 版本链")
def verify_archive_manifest(
    batch_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(archive_service.verify_manifest(user, batch_id))


@router.get("/batches/{batch_id}/corrections", summary="归档后纠错工作队列")
def list_post_archive_corrections(
    batch_id: int = Path(..., gt=0),
    status: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(archive_service.list_correction_cases(user, batch_id, status=status, page=page, page_size=page_size))


@router.get("/corrections/{case_id}", summary="查看归档后纠错证据与正式事实链")
def get_post_archive_correction(
    case_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(archive_service.get_correction_case(user, case_id))


@router.post("/batches/{batch_id}/corrections", summary="发起归档后纠错；不解冻、不改旧 Manifest")
def create_post_archive_correction(
    body: PostArchiveCorrectionCreateBody,
    batch_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(
        archive_service.create_correction_case(
            user,
            batch_id,
            business_type=body.businessType,
            target_ref=body.targetRef,
            reason=body.reason,
            correction=body.correction,
            evidence_manifest=body.evidenceManifest,
            risk_level=body.riskLevel,
        ),
        message="归档后纠错已提交，等待不同操作人二次审批",
    )


@router.post("/corrections/{case_id}/approve", summary="二次审批并追加正式事实 + Manifest V2+")
def approve_post_archive_correction(
    case_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(
        archive_service.approve_correction_case(user, case_id),
        message="归档后纠错已应用并生成新的正式事实与 Manifest 版本",
    )
