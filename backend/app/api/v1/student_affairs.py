"""13A 学工中心 API（/api/v1/student-affairs/*）—— P1：首页三角色视图 + 班级/班干部骨架。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.response import success, paginate
from app.core.security import require_staff
from app.services import affairs_aid_service as aid_svc
from app.services import affairs_dashboard_service as svc
from app.services import affairs_funding_service as funding_svc
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


# ═══════════ 困难认定（P3，aid 全套）═══════════

class AidBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    schoolYear: str = Field(..., min_length=1)
    applyStart: Optional[str] = None
    applyEnd: Optional[str] = None
    publicityDays: Optional[int] = Field(None, description="公示天数（快测可传 0）")
    levelConfig: Optional[dict] = Field(default_factory=dict)
    publish: bool = Field(False)


class AidApplyBody(BaseModel):
    batchId: str = Field(..., min_length=1)
    studentId: str = Field(..., min_length=1)
    applyLevel: str = Field(..., description="SPECIAL/DIFFICULT/GENERAL")
    statement: str = Field(..., description="困难情况说明 10-500 字")
    memberCount: Optional[int] = None
    annualIncome: Optional[str] = Field(None, description="年收入（强敏感，落隔离表）")
    debt: Optional[str] = None
    familyMembers: Optional[list] = Field(default_factory=list)
    specialTags: Optional[list] = Field(default_factory=list)


class AidReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT/RETURN")
    level: Optional[str] = Field(None, description="终审核定/初审建议等级")
    reason: Optional[str] = Field("", max_length=500)


class AidAdjustBody(BaseModel):
    targetLevel: str = Field(..., description="SPECIAL/DIFFICULT/GENERAL")
    reason: str = Field(..., min_length=1)


class AidRevealBody(BaseModel):
    reason: Optional[str] = Field("", description="查看完整家庭经济的原因（落 SENSITIVE 审计）")


@router.post("/aid/batches", summary="建/发布认定批次")
def aid_batch_create(body: AidBatchCreate, user=Depends(require_staff)):
    return success(aid_svc.create_batch(body, user), message="已保存")


@router.get("/aid/batches", summary="认定批次列表")
def aid_batches(schoolYear: Optional[str] = None, status: Optional[str] = None,
                page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = aid_svc.list_batches(user, schoolYear, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/aid/applications", summary="发起困难认定申请（含家庭经济，直达班级评议）")
def aid_apply(body: AidApplyBody, user=Depends(require_staff)):
    return success(aid_svc.apply(body, user), message="已提交")


@router.get("/aid/applications", summary="认定申请列表（家庭经济默认脱敏）")
def aid_applications(batchId: Optional[str] = None, status: Optional[str] = None,
                     level: Optional[str] = None, page: int = 1, pageSize: int = 20,
                     user=Depends(require_staff)):
    items, total = aid_svc.list_applications(user, batchId, status, level, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/aid/difficult-students", summary="困难学生库（供助学金/绿通引用）")
def aid_difficult_students(level: Optional[str] = None, page: int = 1, pageSize: int = 50,
                           user=Depends(require_staff)):
    items, total = aid_svc.difficult_students(user, level, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/aid/applications/{applyId}", summary="认定申请详情（家庭经济脱敏）")
def aid_application(applyId: int = Path(...), user=Depends(require_staff)):
    return success(aid_svc.get_application(applyId, user))


@router.post("/aid/applications/{applyId}/review", summary="各级评审（评议/初审/复审/终审）")
def aid_review(body: AidReviewBody, applyId: int = Path(...), user=Depends(require_staff)):
    return success(aid_svc.review(applyId, user, body.action, body.level, body.reason or ""),
                   message="已处理")


@router.post("/aid/applications/{applyId}/resubmit", summary="退回后重新提交")
def aid_resubmit(applyId: int = Path(...), user=Depends(require_staff)):
    return success(aid_svc.resubmit(applyId, user), message="已重新提交")


@router.post("/aid/applications/{applyId}/publicity-confirm", summary="人工确认公示期满→通过")
def aid_publicity_confirm(applyId: int = Path(...), user=Depends(require_staff)):
    return success(aid_svc.confirm_publicity(applyId, user), message="已通过")


@router.post("/aid/scan-publicity", summary="公示期满扫描（定时/手动，幂等）")
def aid_scan_publicity(user=Depends(require_staff)):
    return success(aid_svc.scan_publicity())


@router.post("/aid/applications/{applyId}/adjust", summary="发起困难等级动态调整")
def aid_adjust(body: AidAdjustBody, applyId: int = Path(...), user=Depends(require_staff)):
    return success(aid_svc.adjust(applyId, user, body.targetLevel, body.reason), message="调整已提交")


@router.post("/aid/applications/{applyId}/adjust-approve", summary="动态调整审批")
def aid_adjust_approve(body: AidReviewBody = None, applyId: int = Path(...), user=Depends(require_staff)):
    action = body.action if body else "APPROVE"
    return success(aid_svc.approve_adjust(applyId, user, action), message="已处理")


@router.post("/aid/applications/{applyId}/reveal", summary="查看完整家庭经济（sensitiveView+审计）")
def aid_reveal(body: AidRevealBody = AidRevealBody(), applyId: int = Path(...),
               user=Depends(require_staff)):
    return success(aid_svc.reveal_family_economy(applyId, user, body.reason or ""))


# ═══════════ 奖助（P3，funding 全套，V1 奖学金/助学金）═══════════

class FundingProjectCreate(BaseModel):
    projectName: str = Field(..., min_length=1)
    projectType: str = Field(..., description="SCHOLARSHIP/GRANT")
    amount: Optional[float] = None
    quota: Optional[int] = None
    conditions: Optional[dict] = Field(default_factory=dict)


class FundingBatchCreate(BaseModel):
    projectId: str = Field(..., min_length=1)
    schoolYear: str = Field(..., min_length=1)
    applyStart: Optional[str] = None
    applyEnd: Optional[str] = None
    publicityDays: Optional[int] = None
    quota: Optional[int] = None
    publish: bool = Field(False)


class FundingApplyBody(BaseModel):
    batchId: str = Field(..., min_length=1)
    studentId: str = Field(..., min_length=1)
    applySource: Optional[str] = Field("SELF", description="SELF/RECOMMEND")
    amount: Optional[float] = None
    statement: Optional[str] = Field("", max_length=1000)


class FundingReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT/RETURN")
    reason: Optional[str] = Field("", max_length=500)


@router.post("/funding/projects", summary="建资助项目（奖学金/助学金）")
def funding_project_create(body: FundingProjectCreate, user=Depends(require_staff)):
    return success(funding_svc.create_project(body, user), message="已创建")


@router.get("/funding/projects", summary="资助项目列表")
def funding_projects(projectType: Optional[str] = None, status: Optional[str] = None,
                     page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = funding_svc.list_projects(user, projectType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/funding/batches", summary="建/发布资助批次")
def funding_batch_create(body: FundingBatchCreate, user=Depends(require_staff)):
    return success(funding_svc.create_batch(body, user), message="已保存")


@router.get("/funding/batches", summary="资助批次列表")
def funding_batches(projectId: Optional[str] = None, status: Optional[str] = None,
                    page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = funding_svc.list_batches(user, projectId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/funding/applications", summary="发起资助申请（含资格硬校验）")
def funding_apply(body: FundingApplyBody, user=Depends(require_staff)):
    return success(funding_svc.apply(body, user), message="已提交")


@router.get("/funding/applications", summary="资助申请列表（金额按角色脱敏）")
def funding_applications(batchId: Optional[str] = None, projectType: Optional[str] = None,
                         status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                         user=Depends(require_staff)):
    items, total = funding_svc.list_applications(user, batchId, projectType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/funding/applications/{applicationId}", summary="资助申请详情（含校验快照）")
def funding_application(applicationId: int = Path(...), user=Depends(require_staff)):
    return success(funding_svc.get_application(applicationId, user))


@router.post("/funding/applications/{applicationId}/review", summary="各级评审")
def funding_review(body: FundingReviewBody, applicationId: int = Path(...), user=Depends(require_staff)):
    return success(funding_svc.review(applicationId, user, body.action, body.reason or ""),
                   message="已处理")


@router.post("/funding/applications/{applicationId}/publicity-confirm", summary="确认公示期满→获资助")
def funding_publicity_confirm(applicationId: int = Path(...), user=Depends(require_staff)):
    return success(funding_svc.confirm_publicity(applicationId, user), message="已通过")


@router.post("/funding/scan-publicity", summary="资助公示扫描（定时/手动，幂等）")
def funding_scan_publicity(user=Depends(require_staff)):
    return success(funding_svc.scan_publicity())
