"""R11 真实学校完整学期试点控制台接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_semester_pilot_service as service

router = APIRouter(prefix="/academic-affairs/semester-pilots", tags=["教务中心-真实学期试点"])


class SemesterPilotCreateBody(BaseModel):
    termId: int = Field(..., gt=0)
    pilotName: str = Field(..., min_length=3, max_length=160)
    purpose: str = Field(..., min_length=5, max_length=500)
    realDataConfirmed: bool = Field(
        ...,
        description="必须人工确认当前租户为真实学校数据；测试/mock数据不得勾选",
    )


class SemesterPilotCompleteBody(BaseModel):
    confirmText: str = Field(..., min_length=1, max_length=80)
    completionNote: str = Field(..., min_length=5, max_length=500)


class SemesterPilotCancelBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


@router.post("", summary="创建真实学校学期试点")
def semester_pilot_create(
    body: SemesterPilotCreateBody,
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(
        service.create_pilot(
            user,
            term_id=body.termId,
            pilot_name=body.pilotName,
            purpose=body.purpose,
            real_data_confirmed=body.realDataConfirmed,
        ),
        message="真实学期试点已创建",
    )


@router.get("", summary="真实学期试点列表")
def semester_pilot_list(
    status: str | None = Query(default=None, max_length=32),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=100),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    rows, total = service.list_pilots(user, status=status, page=page, page_size=pageSize)
    return success({"list": rows, "total": total, "page": page, "pageSize": pageSize})


@router.get("/{pilot_id}", summary="真实学期试点详情与最新六阶段证据")
def semester_pilot_detail(
    pilot_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(service.get_pilot(user, pilot_id))


@router.post("/{pilot_id}/check", summary="按真实租户事实执行六阶段检查")
def semester_pilot_check(
    pilot_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(service.run_check(user, pilot_id), message="六阶段真实证据检查完成")


@router.post("/{pilot_id}/complete", summary="显式确认真实学校完整学期试点完成")
def semester_pilot_complete(
    body: SemesterPilotCompleteBody,
    pilot_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(
        service.complete_pilot(
            user,
            pilot_id,
            confirm_text=body.confirmText,
            completion_note=body.completionNote,
        ),
        message="真实学校完整学期试点已确认完成",
    )


@router.post("/{pilot_id}/cancel", summary="取消未完成试点")
def semester_pilot_cancel(
    body: SemesterPilotCancelBody,
    pilot_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.archive.manage")),
):
    return success(service.cancel_pilot(user, pilot_id, body.reason), message="试点已取消")
