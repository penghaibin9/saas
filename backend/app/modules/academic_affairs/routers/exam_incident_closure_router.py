"""考场异常闭环路由。

与历史大路由分离，避免为了一个P0闭环改动四千行文件。路径仍位于正式
``/academic-affairs/exam/incidents`` 命名空间，权限沿用考场异常管理权限。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_exam_service as service

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-考场异常闭环"])


class IncidentResolveBody(BaseModel):
    action: str = Field(..., description="HANDOFF/CLOSE/VOID")
    reason: Optional[str] = Field(None, max_length=500)
    disciplineCaseRef: Optional[str] = Field(None, max_length=100)


@router.post("/exam/incidents/{incidentId}/resolve", summary="考场异常闭环（移交线索/确认缺考联动/作废误登记）")
def resolve_exam_incident(
    body: IncidentResolveBody,
    incidentId: int = Path(...),
    user=Depends(require_permission("academicAffairs.exam.recordAbnormal")),
):
    return success(
        service.resolve_incident(
            user,
            incidentId,
            body.action,
            body.reason or "",
            body.disciplineCaseRef or "",
        ),
        message="考场异常已处理",
    )
