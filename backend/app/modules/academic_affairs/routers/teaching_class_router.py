"""V2-02 独立教学班及名单版本接口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_teaching_class_query_service as query_service
from app.modules.academic_affairs.services import academic_affairs_teaching_class_admin_service as admin_service
from app.modules.academic_affairs.services import academic_affairs_teaching_class_change_service as change_service

router = APIRouter(prefix="/academic-affairs/teaching-classes", tags=["教务中心-教学班"])

_VIEW = require_permission("academicAffairs.teachingTask.view")
_MANAGE = require_permission("academicAffairs.teachingTask.manage")


class TeachingClassBackfillBody(BaseModel):
    termId: int = Field(..., gt=0)
    dryRun: bool = True
    reason: Optional[str] = Field(default=None, max_length=500)


class TeachingClassRosterPreviewBody(BaseModel):
    studentIds: list[int] = Field(default_factory=list)


class TeachingClassRosterChangeBody(TeachingClassRosterPreviewBody):
    reason: str = Field(..., min_length=5, max_length=500)


@router.get("", summary="教学班列表")
def teaching_class_list(
    termId: Optional[int] = None,
    status: Optional[str] = None,
    classType: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    pageSize: int = 30,
    user=Depends(_VIEW),
):
    items, total = query_service.list_teaching_classes(
        user, termId, status, classType, keyword, page, min(max(pageSize, 1), 200),
    )
    data = paginate(items, total, page, pageSize)
    data["list"] = items
    return success(data)


@router.post("/actions/backfill", summary="教学班存量投影与对账")
def teaching_class_backfill(body: TeachingClassBackfillBody, user=Depends(_MANAGE)):
    result = admin_service.backfill_teaching_classes(
        user, body.termId, body.dryRun, body.reason or "",
    )
    return success(result, message="对账完成" if body.dryRun else "教学班与名单版本回填完成")


@router.post("/{teaching_class_id}/roster/impact", summary="名单变更影响预览")
def teaching_class_roster_impact(
    body: TeachingClassRosterPreviewBody,
    teaching_class_id: int = Path(..., gt=0),
    user=Depends(_MANAGE),
):
    return success(change_service.preview_roster_change(user, teaching_class_id, body.studentIds))


@router.post("/{teaching_class_id}/roster/versions", summary="创建非选课教学班名单版本")
def teaching_class_roster_version_create(
    body: TeachingClassRosterChangeBody,
    teaching_class_id: int = Path(..., gt=0),
    user=Depends(_MANAGE),
):
    result = change_service.create_manual_roster_version(
        user, teaching_class_id, body.studentIds, body.reason,
    )
    return success(result, message="新名单版本已生效")


@router.get("/{teaching_class_id}", summary="教学班详情与名单版本")
def teaching_class_detail(teaching_class_id: int = Path(..., gt=0), user=Depends(_VIEW)):
    return success(query_service.get_teaching_class(user, teaching_class_id))
