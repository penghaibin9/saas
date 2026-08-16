"""考务正式扩展路由。

与历史大路由分离，只承载需要独立 fail-closed 证据边界的考场异常闭环与正式打印读取。
普通 ``/exam/rooms/{roomId}/seats`` 继续服务编排工作区；正式座位表/门贴/准考证必须走
``/exam/rooms/{roomId}/formal-print``，由 C-W3 formal print provider 校验发布状态、冻结名单
与持久化座位全集，禁止把编排草稿伪装成正式文件。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_exam_service as service
from app.modules.academic_affairs.services import academic_affairs_exam_print_service as print_service

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-考务正式扩展"])


class IncidentResolveBody(BaseModel):
    action: str = Field(..., description="HANDOFF/CLOSE/VOID")
    reason: Optional[str] = Field(None, max_length=500)
    disciplineCaseRef: Optional[str] = Field(None, max_length=100)


@router.get("/exam/rooms/{roomId}/formal-print", summary="正式考场座位表/门贴/准考证打印数据")
def formal_exam_room_print(
    roomId: int = Path(...),
    user=Depends(require_permission("academicAffairs.exam.view")),
):
    return success(print_service.formal_room_print(user, roomId))


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