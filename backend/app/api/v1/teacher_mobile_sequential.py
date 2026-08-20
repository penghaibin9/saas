"""Teacher Miniapp V3 T5/T6 single-object internship command adapter.

Every mutation delegates to the canonical internship state machine and carries the exact version
captured with the queue item. T6 only adds a fail-closed risk-confirmation contract; it does not
create a second exception or risk authority.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import AppException
from app.core.permissions import require_module
from app.core.response import success
from app.core.security import require_staff
from app.modules.internship.services import internship_service

router = APIRouter(
    dependencies=[Depends(require_module("internship"))],
)


class AttendanceExceptionHandleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["REASONABLE", "ABNORMAL", "TO_RISK"]
    comment: str = Field(min_length=5, max_length=500)
    expectedVersion: int = Field(ge=0)
    riskLevel: Literal["HIGH"] | None = None


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
    action = str(body.action or "").upper()
    comment = str(body.comment or "").strip()
    if action == "TO_RISK":
        if body.riskLevel != "HIGH":
            raise AppException("VALIDATION_ERROR", "转风险必须显式确认 riskLevel=HIGH")
        if len(comment) < 5:
            raise AppException("VALIDATION_ERROR", "转风险原因不少于 5 字")
    elif body.riskLevel is not None:
        raise AppException("VALIDATION_ERROR", "非转风险操作不得提交 riskLevel")

    return success(
        internship_service.handle_attendance_exception(
            exception_id,
            action,
            comment,
            user=user,
            expected_version=body.expectedVersion,
        ),
        message="处理完成",
    )
