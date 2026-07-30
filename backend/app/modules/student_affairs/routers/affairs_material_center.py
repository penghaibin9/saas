"""阶段 5 学工材料总览、旧数据回填与真实档案 Manifest API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.response import success
from app.core.security import get_current_user
from app.modules.student_affairs.services import affairs_material_center_service as center

router = APIRouter(tags=["学工中心·公共材料与档案"])


class BackfillBody(BaseModel):
    limit: int = Field(500, ge=1, le=5000)


@router.get("/student-affairs/material-center", summary="学校端学工材料总览")
def material_center(
    status: str | None = Query(None),
    sensitivityLevel: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
):
    return success(center.material_overview(
        user, status=status, sensitivity_level=sensitivityLevel,
        page=page, page_size=pageSize,
    ))


@router.post("/student-affairs/material-center/backfill", summary="幂等回填旧学工材料与附件")
def material_backfill(body: BackfillBody, user=Depends(get_current_user)):
    return success(center.backfill_legacy(user, limit=body.limit), message="学工材料回填批次已完成")


@router.get("/student-affairs/archive/packages/{package_id}/manifest", summary="查看学生真实档案版本清单")
def archive_package_manifest(
    package_id: int = Path(..., ge=1),
    user=Depends(get_current_user),
):
    return success(center.get_archive_manifest(package_id, user))
