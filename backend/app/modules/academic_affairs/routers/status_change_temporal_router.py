"""Stage C1 future-effective academic status change entrypoint."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_change_service as change_service

router = APIRouter(prefix="/academic-affairs/status-changes", tags=["学籍异动-计划生效"])


class ScheduledStatusChangeSubmit(BaseModel):
    studentId: str = Field(..., min_length=1)
    changeType: str = Field(
        ...,
        description="SUSPEND/RESUME/WITHDRAW/PRESERVE/RETAIN/TRANSFER_MAJOR/TRANSFER_CLASS",
    )
    reason: Optional[str] = Field("", max_length=500)
    toCollegeId: Optional[str] = None
    toMajorId: Optional[str] = None
    toClassId: Optional[str] = None
    idempotencyKey: Optional[str] = Field(None, max_length=120)
    effectiveDate: str = Field(
        ...,
        min_length=10,
        description="ISO-8601 计划生效时间；必须晚于当前时间。终审通过后先进入待生效态。",
    )


@router.post("/scheduled", summary="发起计划生效的学籍异动；审批通过不提前修改当前学籍")
def submit_scheduled_status_change(
    body: ScheduledStatusChangeSubmit,
    user=Depends(require_permission("academicAffairs.statusChange.apply")),
):
    return success(change_service.submit(body, user), message="计划生效异动已提交")
