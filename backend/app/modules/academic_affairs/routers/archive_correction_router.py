"""Stage C3 immutable archive correction API.

ARCHIVED remains permanent.  These endpoints never reopen a term: they create a
PostArchiveCorrectionCase, require a different second approver, append Manifest V2+
and expose manifest verification.  First production scope is intentionally limited to
GRADE/GRADUATION by the service layer.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Path
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


@router.post("/corrections/{case_id}/approve", summary="二次审批并追加 Manifest V2+；原归档永久保留")
def approve_post_archive_correction(
    case_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(
        archive_service.approve_correction_case(user, case_id),
        message="归档后纠错已应用并生成新的 Manifest 版本",
    )
