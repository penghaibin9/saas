"""13A 学工中心 API（/api/v1/student-affairs/*）—— P1：首页三角色视图 + 班级/班干部骨架。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.response import success, paginate
from app.core.security import require_staff
from app.services import affairs_dashboard_service as svc
from app.services import affairs_leave_service as leave_svc

router = APIRouter(prefix="/student-affairs", tags=["学工中心"])


@router.get("/dashboard", summary="学工首页（三角色视图，按数据范围聚合）")
def dashboard(user=Depends(require_staff)):
    return success(svc.get_dashboard(user))


@router.get("/classes", summary="班级列表（按数据范围）")
def classes(user=Depends(require_staff)):
    return success({"items": svc.list_classes(user)})


@router.get("/classes/{classId}/cadres", summary="班干部列表")
def cadres(classId: int = Path(...), user=Depends(require_staff)):
    return success({"items": svc.list_cadres(classId, user)})


class CadreCreate(BaseModel):
    studentId: str = Field(..., min_length=1, description="学生 id")
    position: str = Field(..., min_length=1, description="职务编码：MONITOR/LEAGUE_SECRETARY/...")
    termCode: Optional[str] = Field(None, description="学年学期编码")


@router.post("/classes/{classId}/cadres", summary="任命班干部")
def add_cadre(body: CadreCreate, classId: int = Path(...), user=Depends(require_staff)):
    return success(svc.add_cadre(classId, body, user), message="已任命")


@router.delete("/classes/cadres/{cadreId}", summary="免去班干部")
def remove_cadre(cadreId: int = Path(...), user=Depends(require_staff)):
    return success(svc.remove_cadre(cadreId, user), message="已免去")


# ═══════════ 请假闭环（P2）═══════════

class LeaveApply(BaseModel):
    studentId: str = Field(..., min_length=1)
    leaveType: str = Field("PERSONAL", description="SICK/PERSONAL/GOOUT")
    startTime: str = Field(..., description="YYYY-MM-DD[ HH:MM:SS]")
    endTime: str = Field(...)
    reason: Optional[str] = Field(None, max_length=500)


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class CommentBody(BaseModel):
    comment: Optional[str] = Field("", max_length=500)


class ExtensionBody(BaseModel):
    newEnd: str = Field(..., description="新结束时间")
    reason: Optional[str] = Field(None, max_length=500)


class CancelBody(BaseModel):
    proofNote: Optional[str] = Field("", max_length=500)


class ConfirmBody(BaseModel):
    note: Optional[str] = Field("", max_length=500)


@router.post("/leave", summary="发起请假")
def leave_apply(body: LeaveApply, user=Depends(require_staff)):
    return success(leave_svc.apply_leave(body, user), message="已提交")


@router.get("/leave/pending", summary="待审批请假（按数据范围）")
def leave_pending(page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = leave_svc.list_pending(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/leave/{leaveId}", summary="请假详情")
def leave_detail(leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.get_detail(leaveId, user))


@router.post("/leave/{leaveId}/approve", summary="请假审批通过（多级逐节点推进）")
def leave_approve(body: CommentBody = CommentBody(), leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.approve(leaveId, user, body.comment or ""), message="已通过")


@router.post("/leave/{leaveId}/reject", summary="请假驳回（原因≥5字，终态）")
def leave_reject(body: ReasonBody, leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.reject(leaveId, user, body.reason), message="已驳回")


@router.post("/leave/{leaveId}/return", summary="请假退回重提（原因≥5字）")
def leave_return(body: ReasonBody, leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.return_leave(leaveId, user, body.reason), message="已退回")


@router.post("/leave/{leaveId}/resubmit", summary="退回后重新提交")
def leave_resubmit(leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.resubmit(leaveId, user), message="已重新提交")


@router.post("/leave/{leaveId}/cancel", summary="发起销假")
def leave_cancel(body: CancelBody = CancelBody(), leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.submit_cancel(leaveId, user, body.proofNote or ""), message="销假已提交")


@router.post("/leave/{leaveId}/cancel-confirm", summary="销假确认（辅导员）→ CLOSED 进360")
def leave_cancel_confirm(body: ConfirmBody = ConfirmBody(), leaveId: int = Path(...),
                         user=Depends(require_staff)):
    return success(leave_svc.confirm_cancel(leaveId, user, body.note or ""), message="已销假")


@router.post("/leave/{leaveId}/extension", summary="发起续假")
def leave_extension(body: ExtensionBody, leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.apply_extension(leaveId, user, body.newEnd, body.reason or ""),
                   message="续假已提交")


@router.post("/leave/{leaveId}/extension-approve", summary="续假审批通过")
def leave_extension_approve(leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.approve_extension(leaveId, user), message="续假已通过")


@router.post("/leave/scan-overdue", summary="逾期扫描（定时/手动触发，幂等）")
def leave_scan_overdue(user=Depends(require_staff)):
    return success(leave_svc.scan_overdue())
