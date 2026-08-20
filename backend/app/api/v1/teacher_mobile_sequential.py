"""Teacher Miniapp V3 T5 single-object sequential command adapter.

This router is additive under the existing ``/teacher-mobile`` surface.  It does not own an
internship state machine: every mutation delegates to the canonical internship service and
requires the exact version captured with the queue item.  That keeps 409/DATA_CONFLICT a real
server-side optimistic-lock signal instead of a UI convention.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.permissions import require_module
from app.core.response import success
from app.core.security import require_staff
from app.modules.internship.services import internship_service

router = APIRouter(
    dependencies=[Depends(require_module("internship"))],
)


class AttendanceExceptionHandleBody(BaseModel):
    action: str
    comment: str
    expectedVersion: int


@router.post(
    "/internship/exceptions/{exception_id}/handle",
    summary="教师端打卡异常逐条处理（乐观锁）",
    name="teacher_mobile_v3_attendance_exception_handle",
)
def handle_attendance_exception(
    exception_id: str,
    body: AttendanceExceptionHandleBody,
    user=Depends(require_staff),
):
    return success(
        internship_service.handle_attendance_exception(
            exception_id,
            str(body.action or "").upper(),
            body.comment or "",
            user=user,
            expected_version=body.expectedVersion,
        ),
        message="处理完成",
    )
