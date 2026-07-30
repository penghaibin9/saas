"""学工材料补交与低风险安全批次 API。

所有旧 URL 保持兼容；材料创建、补交、退回、重交、版本与审核直接调用阶段 5
公共版本 Facade，不再依赖应用启动时替换 service 函数。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.student_affairs.services import affairs_material_center_service as operations

router = APIRouter(tags=["学工中心·材料与安全批次"])


class MaterialRequirementCreate(BaseModel):
    bizType: str = Field(..., min_length=2, max_length=50)
    bizId: int = Field(..., ge=1)
    itemCode: str = Field(..., min_length=1, max_length=100)
    itemName: str = Field(..., min_length=2, max_length=200)
    requirementReason: Optional[str] = Field(None, max_length=500)
    dueAt: Optional[datetime] = None


class MaterialSubmissionCreate(BaseModel):
    fileId: int = Field(..., ge=1)
    note: Optional[str] = Field(None, max_length=500)
    version: int = Field(..., ge=0, description="材料缺项当前乐观锁版本")


class MaterialReviewBody(BaseModel):
    action: str = Field(..., description="ACCEPT/RETURN/WAIVE")
    reason: Optional[str] = Field(None, max_length=500)
    version: int = Field(..., ge=0, description="材料缺项当前乐观锁版本")


class BatchMaterialItem(BaseModel):
    requirementId: int = Field(..., ge=1)
    version: int = Field(..., ge=0, description="该材料缺项当前乐观锁版本")


class BatchJobCreate(BaseModel):
    jobType: str = Field("MATERIAL_REMIND", description="当前仅支持 MATERIAL_REMIND")
    idempotencyKey: str = Field(..., min_length=8, max_length=128)
    items: list[BatchMaterialItem] = Field(..., min_length=1, max_length=200)


@router.post("/student-affairs/material-requirements", summary="教师登记一项材料缺项")
def create_material_requirement(body: MaterialRequirementCreate, user=Depends(get_current_user)):
    return success(operations.create_material_requirement(user, body.model_dump()), message="材料缺项已登记")


@router.get("/student-affairs/material-requirements", summary="教师材料缺项工作队列")
def teacher_material_requirements(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
):
    items, total = operations.list_teacher_requirements(user, status=status, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/student-affairs/material-requirements/{requirement_id}/review", summary="教师验收、退回或免交材料")
def review_material_requirement(
    body: MaterialReviewBody,
    requirement_id: int = Path(..., ge=1),
    user=Depends(get_current_user),
):
    result = operations.review_material(
        user, requirement_id, action=body.action, reason=body.reason or "", expected_version=body.version,
    )
    return success(result, message="材料状态已更新")


@router.get("/mobile/affairs/material-requirements", summary="学生查看本人待补交材料及历史版本")
def my_material_requirements(
    bizType: Optional[str] = Query(None),
    bizId: Optional[int] = Query(None, ge=1),
    user=Depends(get_current_user),
):
    items = operations.list_my_requirements(user, biz_type=bizType, biz_id=bizId)
    return success({"items": items, "total": len(items)})


@router.post("/mobile/affairs/material-requirements/{requirement_id}/submissions", summary="学生补交一个新材料版本")
def submit_material_version(
    body: MaterialSubmissionCreate,
    requirement_id: int = Path(..., ge=1),
    user=Depends(get_current_user),
):
    result = operations.submit_material(
        user, requirement_id, file_id=body.fileId, note=body.note or "", expected_version=body.version,
    )
    return success(result, message="材料已补交，等待老师审核")


@router.post("/student-affairs/batch-jobs", summary="创建并执行低风险安全批次")
def create_batch_job(body: BatchJobCreate, user=Depends(get_current_user)):
    payload = body.model_dump()
    payload["items"] = [item.model_dump() for item in body.items]
    return success(operations.create_batch_job(user, payload), message="批次已执行")


@router.get("/student-affairs/batch-jobs", summary="批次主表列表")
def list_batch_jobs(
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
):
    items, total = operations.list_batch_jobs(user, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/student-affairs/batch-jobs/{job_id}", summary="批次主表及逐条执行结果")
def get_batch_job(job_id: int = Path(..., ge=1), user=Depends(get_current_user)):
    return success(operations.get_batch_job(user, job_id))


@router.post("/student-affairs/batch-jobs/{job_id}/retry-failed", summary="仅重试批次失败项")
def retry_failed_batch_items(job_id: int = Path(..., ge=1), user=Depends(get_current_user)):
    return success(operations.run_batch_job(job_id, user, failed_only=True), message="失败项已重试")
