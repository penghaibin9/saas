"""AA-TERM-01 学期详情工作区、影响预览与安全修改路由。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_term_workspace_service as service

router = APIRouter(prefix="/academic-affairs/terms", tags=["学年学期详情"])
_TERM_VIEW = "academicAffairs.term.view"
_TERM_MANAGE = "academicAffairs.term.manage"


class TermChangeBody(BaseModel):
    termName: Optional[str] = Field(None, max_length=100)
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    teachingWeeks: Optional[int] = Field(None, ge=1, le=30)
    examWeekStart: Optional[int] = Field(None, ge=1, le=30)
    expectedVersion: Optional[int] = Field(None, ge=0)


@router.get("/{termId}/workspace", summary="学期详情工作区：关联业务、允许动作和状态时间线")
def term_workspace(
    termId: int = Path(..., gt=0),
    user=Depends(require_permission(_TERM_VIEW)),
):
    return success(service.get_workspace(termId, user))


@router.post("/{termId}/impact-preview", summary="预览修改学期时间轴对课表、考务、选课和成绩的影响")
def preview_term_change(
    body: TermChangeBody,
    termId: int = Path(..., gt=0),
    user=Depends(require_permission(_TERM_VIEW)),
):
    payload = body.model_dump(exclude_unset=True)
    return success(service.impact_preview(termId, user, payload))


@router.put("/{termId}", summary="安全修改学期基本信息；已发布学期禁止直接修改时间轴")
def update_term(
    body: TermChangeBody,
    termId: int = Path(..., gt=0),
    user=Depends(require_permission(_TERM_MANAGE)),
):
    payload = body.model_dump(exclude_unset=True)
    return success(service.update_term(termId, user, payload), message="学期信息已保存")
