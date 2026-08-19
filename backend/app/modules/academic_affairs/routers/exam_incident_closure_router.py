"""考务正式扩展路由。

与历史大路由分离，只承载需要独立 fail-closed 证据边界的考场异常闭环与正式打印读取/签发。
普通 ``/exam/rooms/{roomId}/seats`` 继续服务编排工作区；正式座位表/门贴/准考证必须走
``/exam/rooms/{roomId}/formal-print``，由 C-W3 formal print provider 校验发布状态、冻结名单
与持久化座位全集，禁止把编排草稿伪装成正式文件。真正触发浏览器打印前再走
``/formal-print/issue`` 写 append-only ``EXAM_TICKET_PRINT`` 审计；预览本身不写审计。

本模块加载时安装五类 C-W3 兼容 guard：
- 发布通知 guard 包装 legacy ``_notify_publish``，让原学生通知继续原样执行，并在同事务把当前
  canonical 监考行投递给真实教师账号；发布状态机和监考 Assignment 仍由既有 exam facade 唯一持有；
- legacy ``GET /exam/incidents`` 保留 URL，但读模型重绑到同一个全生命周期 workbench，避免旧入口
  只读 ACTIVE、整表 materialize 后 Python 分页，与新闭环事实产生双口径；
- 监考教师登记异常的 scope 只认当前未删除 Assignment + ACTIVE room，软删旧行/失效考场不再保留写权限；
- 已发布 ``/mobile/academic/exam/*`` 的考试安排/缓考选课/缓考提交重绑到学生正式 seat 事实链，
  保留原 URL 与缓考审批状态机，不再消费 UTC 判断、失效考场或可猜 examCourseId 的旧实现；
- legacy/PC ``defer_apply`` service 本身也重绑到同一正式 seat 命令，确保 exam_core 与旧大路由
  不会成为移动端之外的第二条弱校验写入口。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_exam_incident_workbench_service as incident_workbench
from app.modules.academic_affairs.services import academic_affairs_exam_invigilator_scope_guard as invigilator_scope_guard
from app.modules.academic_affairs.services import academic_affairs_exam_service as service
from app.modules.academic_affairs.services import academic_affairs_exam_print_service as print_service
from app.modules.academic_affairs.services import academic_affairs_exam_publish_delivery_guard as publish_delivery_guard
from app.modules.academic_affairs.services import student_exam_legacy_binding_guard as student_exam_legacy_guard
from app.modules.academic_affairs.services import student_exam_read_service as student_exam_safe
from app.services.db_service import session


def _legacy_incident_list(user, batch_id=None, page=1, page_size=50):
    """Published legacy route adapter: same URL, canonical lifecycle workbench truth."""
    with session() as db:
        result = incident_workbench.project_incident_workbench(
            db,
            user,
            batch_id=int(batch_id) if batch_id not in (None, "") else None,
            view="ALL",
            page=max(1, int(page or 1)),
            page_size=min(100, max(1, int(page_size or 50))),
        )
        return result.get("items") or [], int(result.get("total") or 0)


_legacy_incident_list._exam_incident_workbench_compat = True


def _install_legacy_incident_read() -> None:
    if not hasattr(service, "_c_w3_original_list_incidents"):
        service._c_w3_original_list_incidents = service.list_incidents
    service.list_incidents = _legacy_incident_list


publish_delivery_guard.install()
invigilator_scope_guard.install()
_install_legacy_incident_read()
student_exam_safe.install_mobile_facade()
student_exam_legacy_guard.install()

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-考务正式扩展"])


class IncidentResolveBody(BaseModel):
    action: str = Field(..., description="HANDOFF/CLOSE/VOID")
    reason: Optional[str] = Field(None, max_length=500)
    disciplineCaseRef: Optional[str] = Field(None, max_length=100)


class FormalPrintIssueBody(BaseModel):
    documentKind: str = Field(..., pattern="^(DOOR_LIST|TICKET)$")
    studentNo: Optional[str] = Field(default=None, max_length=50)
    reason: Optional[str] = Field(default=None, max_length=500)


@router.get("/exam/rooms/{roomId}/formal-print", summary="正式考场座位表/门贴/准考证打印数据")
def formal_exam_room_print(
    roomId: int = Path(...),
    user=Depends(require_permission("academicAffairs.exam.view")),
):
    return success(print_service.formal_room_print(user, roomId))


@router.post("/exam/rooms/{roomId}/formal-print/issue", summary="记录正式打印/补打审计后签发打印动作")
def issue_formal_exam_room_print(
    body: FormalPrintIssueBody,
    roomId: int = Path(...),
    user=Depends(require_permission("academicAffairs.exam.view")),
):
    return success(
        print_service.record_formal_print(
            user,
            roomId,
            document_kind=body.documentKind,
            student_no=body.studentNo,
            reason=body.reason or "",
        ),
        message="补打审计已记录" if (body.reason or "").strip() else "打印审计已记录",
    )


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