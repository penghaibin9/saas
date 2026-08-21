"""Teacher Miniapp V3 T7 employment recommendation / destination verification routes."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import require_module, require_permission
from app.core.response import success
from app.services import teacher_mobile_employment_service as svc
from app.services import teacher_mobile_employment_stats_service as stats_svc

router = APIRouter(
    prefix="/employment",
    tags=["teacher-mobile-employment-v3"],
    dependencies=[Depends(require_module("employment"))],
)


class _StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecommendationBody(_StrictBody):
    jobId: int = Field(gt=0)
    reason: str = Field(min_length=5, max_length=500)
    note: str | None = Field(default=None, max_length=1000)
    expectedStudentVersion: int = Field(ge=0)


class MaterialEvidenceBody(_StrictBody):
    fileId: str = Field(min_length=1, max_length=64)
    expectedVersion: int = Field(ge=0)


class VerificationReviewBody(_StrictBody):
    action: Literal["VERIFY", "RETURN"]
    comment: str | None = Field(default=None, max_length=500)
    expectedVersion: int = Field(ge=0)


@router.get("/overview", summary="教师端就业推荐/核验工作区")
def employment_overview(user=Depends(require_permission("employment.student.view"))):
    payload = svc.overview(user)
    payload["stats"] = stats_svc.exact_stats(user=user)
    return success(payload)


@router.post("/students/{student_id}/recommendations", summary="单学生岗位推荐")
def create_recommendation(
    student_id: int,
    body: RecommendationBody,
    user=Depends(require_permission("employment.unemployed.manage")),
):
    return success(
        svc.create_recommendation(user, student_id, body.model_dump(exclude_none=True)),
        message="岗位推荐已记录",
    )


@router.get("/students/{student_id}/verification", summary="单学生去向/材料核验详情")
def verification_detail(
    student_id: int,
    user=Depends(require_permission("employment.material.view")),
):
    return success(svc.get_verification(user, student_id))


@router.post("/materials/{material_id}/evidence", summary="绑定就业材料正式文件证据")
def bind_material_evidence(
    material_id: int,
    body: MaterialEvidenceBody,
    user=Depends(require_permission("employment.material.approve")),
):
    return success(
        svc.bind_material_evidence(user, material_id, body.model_dump()),
        message="就业材料正式证据已绑定",
    )


@router.post("/verifications/{verification_id}/review", summary="单学生去向核验")
def review_verification(
    verification_id: int,
    body: VerificationReviewBody,
    user=Depends(require_permission("employment.material.approve")),
):
    return success(
        svc.review_verification(user, verification_id, body.model_dump(exclude_none=True)),
        message="去向核验结果已保存",
    )
