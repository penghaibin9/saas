"""考务正式扩展路由。

与历史大路由分离，只承载需要独立 fail-closed 证据边界的考场异常闭环与正式打印读取。
普通 ``/exam/rooms/{roomId}/seats`` 继续服务编排工作区；正式座位表/门贴/准考证必须走
``/exam/rooms/{roomId}/formal-print``，由 C-W3 formal print provider 校验发布状态、冻结名单
与持久化座位全集，禁止把编排草稿伪装成正式文件。

本模块加载时只安装 C-W3 发布通知 guard：它包装 legacy ``_notify_publish``，让原学生通知继续
原样执行，并在同事务把当前 canonical 监考行投递给真实教师账号；发布状态机和监考 Assignment
仍由既有 exam facade 唯一持有。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_exam_incident_workbench_service as incident_workbench
from app.modules.academic_affairs.services import academic_affairs_exam_service as service
from app.modules.academic_affairs.services import academic_affairs_exam_print_service as print_service
from app.modules.academic_affairs.services import academic_affairs_exam_publish_delivery_guard as publish_delivery_guard
from app.services.db_service import session

publish_delivery_guard.install()

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


@router.get("/exam/incidents/workbench", summary="考场异常全生命周期工作台（含闭环/作废历史）")
def exam_incident_workbench(
    batchId: Optional[int] = Query(None),
    view: str = Query("ALL", pattern="^(ALL|OPEN|CLOSED|VOIDED)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    user=Depends(require_permission("academicAffairs.exam.view")),
):
    with session() as db:
        return success(
            incident_workbench.project_incident_workbench(
                db,
                user,
                batch_id=batchId,
                view=view,
                page=page,
                page_size=pageSize,
            )
        )


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