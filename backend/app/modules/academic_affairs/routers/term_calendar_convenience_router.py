"""D1-U 学期/校历/作息便利性辅助 Router。

仅提供 preview/read-side 能力；不创建第二套正式写入口。
页面确认后继续调用现有校历事件/节次 canonical API，并由服务端最终重检。
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_term_calendar_convenience_service as convenience


router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])


class CalendarCopyPreviewBody(BaseModel):
    sourceTermId: int


class TimeSlotTemplatePreviewBody(BaseModel):
    templateKey: Literal["STANDARD_8", "STANDARD_10"]


@router.post("/terms/{termId}/calendar/copy-preview", summary="复制上一学期校历·预览（不落库）")
def calendar_copy_preview(
    body: CalendarCopyPreviewBody,
    termId: int = Path(...),
    user=Depends(require_permission("academicAffairs.calendar.manage")),
):
    return success(convenience.calendar_copy_preview(termId, body.sourceTermId, user))


@router.post("/time-slots/template-preview", summary="标准 8/10 节作息模板·冲突预览（不落库）")
def time_slot_template_preview(
    body: TimeSlotTemplatePreviewBody,
    user=Depends(require_permission("academicAffairs.timeslot.manage")),
):
    return success(convenience.time_slot_template_preview(body.templateKey, user))
