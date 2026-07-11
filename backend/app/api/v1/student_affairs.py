"""13A 学工中心 API（/api/v1/student-affairs/*）—— P1：首页三角色视图 + 班级/班干部骨架。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.response import success, paginate
from app.core.security import require_staff
from app.services import affairs_aid_service as aid_svc
from app.services import affairs_archive_service as archive_svc
from app.services import affairs_class_service as class_svc
from app.services import affairs_dashboard_service as svc
from app.services import affairs_discipline_service as disc_svc
from app.services import affairs_dorm_service as dorm_svc
from app.services import affairs_funding_service as funding_svc
from app.services import affairs_leave_service as leave_svc
from app.services import affairs_profile_service as profile_svc
from app.services import affairs_risk_service as risk_svc
from app.services import affairs_talk_service as talk_svc

router = APIRouter(prefix="/student-affairs", tags=["学工中心"])


@router.get("/dashboard", summary="学工首页（三角色视图，按数据范围聚合）")
def dashboard(user=Depends(require_staff)):
    return success(svc.get_dashboard(user))


@router.get("/classes", summary="班级列表（名称+指标，按数据范围，可筛学院/专业/年级/关键词）")
def classes(collegeId: Optional[str] = None, majorId: Optional[str] = None,
            grade: Optional[str] = None, keyword: Optional[str] = None,
            page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = class_svc.class_list(user, collegeId, majorId, grade, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/classes/{classId}/profile", summary="班级画像（人数/男女/请假/风险/困难/处分/班干部/材料聚合）")
def class_profile(classId: int = Path(...), user=Depends(require_staff)):
    return success(class_svc.class_profile(classId, user))


@router.get("/classes/{classId}/students", summary="班级学生列表（联系方式脱敏）")
def class_students(classId: int = Path(...), keyword: Optional[str] = None,
                   page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = class_svc.class_students(classId, user, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


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


# ── 班级材料 ──

class MaterialCreate(BaseModel):
    materialType: str = Field(..., description="CLASS_MEETING/THEME_ACTIVITY/EVALUATION/ATTENDANCE/SUMMARY/OTHER")
    title: str = Field(..., min_length=1, max_length=200)
    fileId: Optional[str] = Field(None, description="附件 file_id（文件中心）")
    fileName: Optional[str] = None
    materialAt: Optional[str] = Field(None, description="材料日期 YYYY-MM-DD")
    remark: Optional[str] = Field(None, max_length=500)


@router.get("/classes/{classId}/materials", summary="班级材料列表")
def class_materials(classId: int = Path(...), materialType: Optional[str] = None,
                    page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = class_svc.list_materials(classId, user, materialType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/classes/{classId}/materials", summary="新增班级材料（附件走文件中心 file_id）")
def add_class_material(body: MaterialCreate, classId: int = Path(...), user=Depends(require_staff)):
    return success(class_svc.add_material(classId, user, body), message="已新增")


@router.delete("/classes/materials/{materialId}", summary="作废班级材料（逻辑删除）")
def void_class_material(materialId: int = Path(...), user=Depends(require_staff)):
    return success(class_svc.void_material(materialId, user), message="已作废")


# ── 辅导员考评 ──

class PeriodCreate(BaseModel):
    periodName: str = Field(..., min_length=1, max_length=100)
    semester: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=500)


class ScoreBody(BaseModel):
    collegeScore: float = Field(..., ge=0, le=100, description="学院评分 0-100")


@router.post("/counselor-assessment/periods", summary="新建辅导员考评周期")
def counselor_period_create(body: PeriodCreate, user=Depends(require_staff)):
    return success(class_svc.create_period(user, body.periodName, body.semester, body.remark),
                   message="已创建")


@router.get("/counselor-assessment/periods", summary="考评周期列表")
def counselor_periods(page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = class_svc.list_periods(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/counselor-assessment/periods/{periodId}/collect", summary="生成/刷新考评指标（系统抓取工作量，幂等）")
def counselor_collect(periodId: int = Path(...), user=Depends(require_staff)):
    return success(class_svc.collect_assessments(periodId, user), message="已生成")


@router.get("/counselor-assessment/periods/{periodId}/assessments", summary="考评记录（含自动指标+评分+排名）")
def counselor_assessments(periodId: int = Path(...), user=Depends(require_staff)):
    return success({"items": class_svc.list_assessments(periodId, user)})


@router.post("/counselor-assessment/periods/{periodId}/publish", summary="发布考评周期")
def counselor_publish(periodId: int = Path(...), user=Depends(require_staff)):
    return success(class_svc.publish_period(periodId, user), message="已发布")


@router.post("/counselor-assessment/assessments/{assessmentId}/score", summary="学院评分（综合分=自动*0.6+学院*0.4）")
def counselor_score(body: ScoreBody, assessmentId: int = Path(...), user=Depends(require_staff)):
    return success(class_svc.score_assessment(assessmentId, user, body.collegeScore), message="已评分")


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


class ExtensionReviewBody(BaseModel):
    action: str = Field("APPROVE", description="APPROVE 续假通过 / REJECT 续假驳回")
    reason: Optional[str] = Field("", max_length=500, description="驳回原因≥5字")


class CancelBody(BaseModel):
    proofNote: Optional[str] = Field("", max_length=500)


class ProxyCancelBody(BaseModel):
    actualReturnAt: str = Field(..., description="实际返校时间 YYYY-MM-DD[ HH:MM:SS]")
    note: Optional[str] = Field("", max_length=500)


class OverdueHandleBody(BaseModel):
    handleType: str = Field(..., description="CONTACT 联系 / TO_HOME_SCHOOL 转家校 / CLOSE 处置关闭")
    note: str = Field(..., min_length=1, description="处置说明≥5字")


class ConfirmBody(BaseModel):
    action: str = Field("CONFIRM", description="CONFIRM 销假确认 / RETURN 销假退回")
    actualReturnAt: Optional[str] = Field(None, description="确认时可校对实际返校时间")
    reason: Optional[str] = Field("", max_length=500, description="退回原因≥5字")
    note: Optional[str] = Field("", max_length=500)


@router.post("/leave", summary="发起请假")
def leave_apply(body: LeaveApply, user=Depends(require_staff)):
    return success(leave_svc.apply_leave(body, user), message="已提交")


@router.get("/leave/pending", summary="待审批请假（按数据范围）")
def leave_pending(page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = leave_svc.list_pending(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/leave", summary="请假台账（全状态，按数据范围，可筛类型/班级/关键词/日期）")
def leave_ledger(status: Optional[str] = None, leaveType: Optional[str] = None,
                 classId: Optional[str] = None, keyword: Optional[str] = None,
                 dateStart: Optional[str] = None, dateEnd: Optional[str] = None,
                 followupOnly: bool = False, page: int = 1, pageSize: int = 20,
                 user=Depends(require_staff)):
    items, total = leave_svc.list_leaves(user, status, leaveType, classId, keyword,
                                         dateStart, dateEnd, followupOnly, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/leave/stats", summary="请假统计（人数/天数/逾期未销，按班级/类型/状态下钻）")
def leave_stats(groupBy: str = "CLASS", dateStart: Optional[str] = None,
                dateEnd: Optional[str] = None, user=Depends(require_staff)):
    return success(leave_svc.leave_stats(user, groupBy, dateStart, dateEnd))


@router.post("/leave/export", summary="请假台账导出（xlsx 水印 + 导出留痕）")
def leave_export(status: Optional[str] = None, leaveType: Optional[str] = None,
                 classId: Optional[str] = None, keyword: Optional[str] = None,
                 dateStart: Optional[str] = None, dateEnd: Optional[str] = None,
                 user=Depends(require_staff)):
    return success(leave_svc.export_leaves(user, status, leaveType, classId, keyword,
                                           dateStart, dateEnd))


@router.get("/leave/{leaveId}", summary="请假详情（含销假/续假记录 + 审批留痕）")
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


@router.post("/leave/{leaveId}/cancel-confirm", summary="销假确认/退回（辅导员）→ CLOSED 进360 / 退回 APPROVED")
def leave_cancel_confirm(body: ConfirmBody = ConfirmBody(), leaveId: int = Path(...),
                         user=Depends(require_staff)):
    r = leave_svc.confirm_cancel(leaveId, user, action=body.action,
                                 actual_return_at=body.actualReturnAt, reason=body.reason or "",
                                 note=body.note or "")
    return success(r, message="已退回" if (body.action or "").upper() == "RETURN" else "已销假")


@router.post("/leave/{leaveId}/proxy-cancel", summary="辅导员代登记销假 → WAIT_CANCEL_LEAVE")
def leave_proxy_cancel(body: ProxyCancelBody, leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.proxy_cancel(leaveId, user, body.actualReturnAt, body.note or ""),
                   message="已代登记销假")


@router.post("/leave/{leaveId}/overdue-handle", summary="逾期处置登记（联系/转家校/处置关闭）")
def leave_overdue_handle(body: OverdueHandleBody, leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.handle_overdue(leaveId, user, body.handleType, body.note),
                   message="已登记")


@router.post("/leave/{leaveId}/extension", summary="发起续假")
def leave_extension(body: ExtensionBody, leaveId: int = Path(...), user=Depends(require_staff)):
    return success(leave_svc.apply_extension(leaveId, user, body.newEnd, body.reason or ""),
                   message="续假已提交")


@router.post("/leave/{leaveId}/extension-approve", summary="续假审批（通过/驳回）")
def leave_extension_approve(body: ExtensionReviewBody = ExtensionReviewBody(), leaveId: int = Path(...),
                            user=Depends(require_staff)):
    r = leave_svc.approve_extension(leaveId, user, action=body.action, reason=body.reason or "")
    return success(r, message="续假已驳回" if (body.action or "").upper() == "REJECT" else "续假已通过")


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


# ═══════════ 违纪处分（P4，discipline 全套）═══════════

class DisciplineRegister(BaseModel):
    studentId: str = Field(..., min_length=1)
    discType: str = Field(..., description="WARNING/SERIOUS_WARNING/DEMERIT/PROBATION/EXPEL")
    reason: str = Field(..., min_length=1, description="违纪事实≥5字")
    docNo: Optional[str] = None


class DiscReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT/RETURN")
    reason: Optional[str] = Field("", max_length=500)


class DiscRemoveBody(BaseModel):
    reason: str = Field(..., min_length=1, description="解除理由≥5字")


@router.post("/discipline/cases", summary="登记违纪处分")
def discipline_register(body: DisciplineRegister, user=Depends(require_staff)):
    return success(disc_svc.register(body, user), message="已登记")


@router.get("/discipline/cases", summary="处分列表（学生端仅数量，此为教师侧明细）")
def discipline_cases(status: Optional[str] = None, discType: Optional[str] = None,
                     page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = disc_svc.list_cases(user, status, discType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/discipline/reconcile", summary="处分投影一致性对账")
def discipline_reconcile(user=Depends(require_staff)):
    return success(disc_svc.projection_reconcile())


@router.get("/discipline/cases/{caseId}", summary="处分详情")
def discipline_case(caseId: int = Path(...), user=Depends(require_staff)):
    return success(disc_svc.get_case(caseId, user))


@router.post("/discipline/cases/{caseId}/submit", summary="提交学院初审")
def discipline_submit(caseId: int = Path(...), user=Depends(require_staff)):
    return success(disc_svc.submit(caseId, user), message="已提交")


@router.post("/discipline/cases/{caseId}/cancel", summary="撤销登记")
def discipline_cancel(caseId: int = Path(...), user=Depends(require_staff)):
    return success(disc_svc.cancel(caseId, user), message="已撤销")


@router.post("/discipline/cases/{caseId}/review", summary="处分审批（学院初审/学工处复核/校级）")
def discipline_review(body: DiscReviewBody, caseId: int = Path(...), user=Depends(require_staff)):
    return success(disc_svc.review(caseId, user, body.action, body.reason or ""), message="已处理")


@router.post("/discipline/cases/{caseId}/remove", summary="发起处分解除申请")
def discipline_remove(body: DiscRemoveBody, caseId: int = Path(...), user=Depends(require_staff)):
    return success(disc_svc.submit_remove(caseId, user, body.reason), message="解除已提交")


@router.post("/discipline/cases/{caseId}/remove-review", summary="处分解除审批（辅→院→处）")
def discipline_remove_review(body: DiscReviewBody, caseId: int = Path(...), user=Depends(require_staff)):
    return success(disc_svc.review_remove(caseId, user, body.action, body.reason or ""), message="已处理")


# ═══════════ 风险预警（P4，risk 全套）═══════════

class RiskCreate(BaseModel):
    studentId: str = Field(..., min_length=1)
    source: str = Field(..., description="LEAVE_OVERDUE/ACADEMIC_WARNING/DORM/MENTAL/DISCIPLINE/...")
    sourceRefId: Optional[str] = None
    riskLevel: str = Field("MEDIUM", description="LOW/MEDIUM/HIGH/CRITICAL")
    title: Optional[str] = None
    detail: Optional[str] = None


class RiskAssignBody(BaseModel):
    ownerId: str = Field(..., min_length=1)


class RiskContentBody(BaseModel):
    content: Optional[str] = Field("", max_length=1000)


class RiskTransferBody(BaseModel):
    newOwnerId: str = Field(..., min_length=1)
    reason: Optional[str] = Field("", max_length=500)


class RiskReasonBody(BaseModel):
    reason: Optional[str] = Field("", max_length=500)


class RiskCloseBody(BaseModel):
    conclusion: str = Field(..., min_length=1, description="关闭结论≥5字")


@router.post("/risk/records", summary="建风险记录（多来源，去重）")
def risk_create(body: RiskCreate, user=Depends(require_staff)):
    return success(risk_svc.create_risk(body, user), message="已建单")


@router.get("/risk/records", summary="风险列表（心理来源明细按角色）")
def risk_records(source: Optional[str] = None, status: Optional[str] = None,
                 riskLevel: Optional[str] = None, page: int = 1, pageSize: int = 20,
                 user=Depends(require_staff)):
    items, total = risk_svc.list_risks(user, source, status, riskLevel, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/risk/records/{riskId}", summary="风险详情")
def risk_record(riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.get_risk(riskId, user))


@router.post("/risk/records/{riskId}/assign", summary="分派责任人")
def risk_assign(body: RiskAssignBody, riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.assign(riskId, user, body.ownerId), message="已分派")


@router.post("/risk/records/{riskId}/process", summary="处置（首条→PROCESSING）")
def risk_process(body: RiskContentBody, riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.process(riskId, user, body.content or ""), message="已处置")


@router.post("/risk/records/{riskId}/follow", summary="转持续跟进")
def risk_follow(body: RiskContentBody = RiskContentBody(), riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.follow(riskId, user, body.content or ""), message="已转跟进")


@router.post("/risk/records/{riskId}/transfer", summary="转办（换责任人）")
def risk_transfer(body: RiskTransferBody, riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.transfer(riskId, user, body.newOwnerId, body.reason or ""), message="已转办")


@router.post("/risk/records/{riskId}/escalate", summary="升级")
def risk_escalate(body: RiskReasonBody = RiskReasonBody(), riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.escalate(riskId, user, body.reason or ""), message="已升级")


@router.post("/risk/records/{riskId}/takeover", summary="上级接管")
def risk_takeover(body: RiskContentBody = RiskContentBody(), riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.takeover(riskId, user, body.content or ""), message="已接管")


@router.post("/risk/records/{riskId}/close", summary="关闭（结论≥5字，进360）")
def risk_close(body: RiskCloseBody, riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.close(riskId, user, body.conclusion), message="已关闭")


@router.post("/risk/records/{riskId}/reopen", summary="复发重开")
def risk_reopen(body: RiskReasonBody = RiskReasonBody(), riskId: int = Path(...), user=Depends(require_staff)):
    return success(risk_svc.reopen(riskId, user, body.reason or ""), message="已重开")


@router.post("/risk/scan-timeout", summary="风险超时扫描（分派/升级，幂等）")
def risk_scan_timeout(user=Depends(require_staff)):
    return success(risk_svc.scan_timeout())


# ═══════════ 谈心谈话 + 家校 + 画像/时间线（P5）═══════════

class TalkCreate(BaseModel):
    studentIds: list[str] = Field(..., min_length=1)
    talkType: str = Field(..., description="DAILY/ACADEMIC/PSYCHOLOGY/DISCIPLINE/...")
    topic: str = Field(..., min_length=1)
    scheduledAt: Optional[str] = None


class TalkRecordBody(BaseModel):
    content: str = Field(..., min_length=1, description="谈话内容≥20字")
    result: Optional[str] = Field("", max_length=50)
    needFollowUp: bool = Field(False)


class TalkFollowBody(BaseModel):
    action: str = Field(..., description="FOLLOW/CLOSE/TO_RISK/TO_HOME_SCHOOL")
    content: Optional[str] = Field("", max_length=1000)


class ContactCreate(BaseModel):
    contactType: str = Field("PHONE", description="PHONE/WECHAT/VISIT/MESSAGE")
    reason: Optional[str] = Field("", max_length=500)
    result: Optional[str] = Field("", max_length=1000)
    fullPhoneView: bool = Field(False, description="是否查看完整号码")
    viewReason: Optional[str] = Field("", description="查看完整号码原因≥5字")


@router.get("/students/{studentId}/profile", summary="学工画像（各域沉淀汇总）")
def student_profile(studentId: int = Path(...), user=Depends(require_staff)):
    return success(profile_svc.get_profile(studentId, user))


@router.get("/students/{studentId}/timeline", summary="成长时间线（360，各域进360事件倒序）")
def student_timeline(studentId: int = Path(...), eventType: Optional[str] = None,
                     page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = profile_svc.get_timeline(studentId, user, eventType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/talks", summary="谈话列表（管理侧默认摘要，心理类按权限）")
def talks(talkType: Optional[str] = None, status: Optional[str] = None,
          studentId: Optional[str] = None, page: int = 1, pageSize: int = 20,
          user=Depends(require_staff)):
    items, total = talk_svc.list_talks(user, talkType, status, studentId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/talks", summary="建谈话计划（批量圈定学生）")
def talk_create(body: TalkCreate, user=Depends(require_staff)):
    return success(talk_svc.create_talk(body, user), message="已创建")


@router.get("/talks/stats", summary="谈话工作量统计（完成率）")
def talk_stats(groupBy: str = "TYPE", user=Depends(require_staff)):
    return success(talk_svc.talk_stats(user, groupBy))


@router.get("/talks/{talkId}", summary="谈话详情（心理类全文按权限）")
def talk_detail(talkId: int = Path(...), user=Depends(require_staff)):
    return success(talk_svc.get_talk(talkId, user))


@router.post("/talks/{talkId}/record", summary="填写谈话记录（→COMPLETED，进360）")
def talk_record(body: TalkRecordBody, talkId: int = Path(...), user=Depends(require_staff)):
    return success(talk_svc.record_talk(talkId, user, body.content, body.result or "", body.needFollowUp),
                   message="已记录")


@router.post("/talks/{talkId}/follow-up", summary="跟进/办结/转风险/转家校")
def talk_follow(body: TalkFollowBody, talkId: int = Path(...), user=Depends(require_staff)):
    return success(talk_svc.follow_up(talkId, user, body.action, body.content or ""), message="已处理")


@router.get("/students/{studentId}/family-contacts", summary="家校联系记录列表")
def family_contacts(studentId: int = Path(...), page: int = 1, pageSize: int = 20,
                    user=Depends(require_staff)):
    items, total = talk_svc.list_contacts(studentId, user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/students/{studentId}/family-contacts", summary="登记家校联系（完整号码必填原因+审计）")
def family_contact_create(body: ContactCreate, studentId: int = Path(...), user=Depends(require_staff)):
    return success(talk_svc.create_contact(studentId, user, body), message="已登记")


# ═══════════ 宿舍房源台账（P6，楼/房/床 + 选床 + 调宿 + 检查）═══════════

class BuildingCreate(BaseModel):
    buildingName: str = Field(..., min_length=1, description="楼栋名称，如 紫荆1号楼")
    buildingCode: Optional[str] = None
    genderLimit: str = Field("MIXED", description="MALE/FEMALE/MIXED")
    managerTeacherKey: Optional[str] = None
    floorCount: Optional[int] = None
    # 一步到位：带上以下三参数则建楼即铺满床位
    floors: Optional[int] = Field(None, description="层数（带上则一键铺床）")
    roomsPerFloor: Optional[int] = Field(None, description="每层房间数")
    bedsPerRoom: Optional[int] = Field(None, description="每间床位数")


class GenerateBody(BaseModel):
    floors: int = Field(..., ge=1, description="层数")
    roomsPerFloor: int = Field(..., ge=1, description="每层房间数")
    bedsPerRoom: int = Field(..., ge=1, description="每间床位数")


class CheckinBody(BaseModel):
    studentId: str = Field(..., min_length=1)


class TransferSubmit(BaseModel):
    studentId: str = Field(..., min_length=1)
    toBedId: str = Field(..., min_length=1)
    reason: Optional[str] = Field("", max_length=500)


class DormReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    reason: Optional[str] = Field("", max_length=500)


class CheckTaskCreate(BaseModel):
    taskName: str = Field(..., min_length=1)
    buildingId: Optional[str] = None
    checkType: str = Field("HYGIENE", description="HYGIENE/SAFETY/CONTRABAND/NIGHT_ABSENCE")
    checkerKey: Optional[str] = None


class CheckRecordBody(BaseModel):
    roomId: Optional[str] = None
    result: str = Field(..., description="NORMAL/ABNORMAL")
    issueType: Optional[str] = None
    detail: Optional[str] = Field("", max_length=1000)


@router.post("/dorm/buildings", summary="新建楼栋（带层数/房数/床位则一键铺满）")
def dorm_building_create(body: BuildingCreate, user=Depends(require_staff)):
    return success(dorm_svc.create_building(body, user), message="已创建")


@router.get("/dorm/buildings", summary="楼栋列表（选床级联1；gender 过滤）")
def dorm_buildings(gender: Optional[str] = None, page: int = 1, pageSize: int = 50,
                   user=Depends(require_staff)):
    items, total = dorm_svc.list_buildings(user, gender, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/dorm/buildings/{buildingId}/generate", summary="铺房+床（层数×每层房数×每间床位）")
def dorm_generate(body: GenerateBody, buildingId: int = Path(...), user=Depends(require_staff)):
    return success(dorm_svc.generate_layout(buildingId, user, body.floors, body.roomsPerFloor,
                                            body.bedsPerRoom), message="已铺床位")


@router.get("/dorm/buildings/{buildingId}/rooms", summary="房间列表（选床级联2；floor 过滤，带空床数）")
def dorm_rooms(buildingId: int = Path(...), floor: Optional[int] = None, page: int = 1,
               pageSize: int = 100, user=Depends(require_staff)):
    items, total = dorm_svc.list_rooms(buildingId, user, floor, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/dorm/rooms/{roomId}/beds", summary="床位列表（选床级联3；标空/已住）")
def dorm_beds(roomId: int = Path(...), user=Depends(require_staff)):
    return success({"items": dorm_svc.list_beds(roomId, user)})


@router.get("/dorm/occupancy", summary="宿舍入住率统计")
def dorm_occupancy(user=Depends(require_staff)):
    return success(dorm_svc.occupancy_stats(user))


@router.post("/dorm/beds/{bedId}/checkin", summary="学生入住某床（回写我的宿舍）")
def dorm_checkin(body: CheckinBody, bedId: int = Path(...), user=Depends(require_staff)):
    return success(dorm_svc.checkin(bedId, user, body.studentId), message="已入住")


@router.post("/dorm/beds/{bedId}/checkout", summary="退宿（释放床位）")
def dorm_checkout(bedId: int = Path(...), user=Depends(require_staff)):
    return success(dorm_svc.checkout(bedId, user), message="已退宿")


class DormConfigBody(BaseModel):
    enabled: bool = Field(..., description="是否放开学生自选宿舍（true=学生自选，false=辅导员分配）")


@router.get("/dorm/config", summary="宿舍分配模式（学生自选是否放开）")
def dorm_config(user=Depends(require_staff)):
    return success(dorm_svc.get_dorm_config(user))


@router.put("/dorm/config/self-select", summary="学校开/关学生自选宿舍")
def dorm_set_self_select(body: DormConfigBody, user=Depends(require_staff)):
    return success(dorm_svc.set_self_select(user, body.enabled),
                   message=("已放开学生自选" if body.enabled else "已切换为辅导员分配"))


@router.post("/dorm/beds/{bedId}/self-select", summary="学生自选床位入住（需学校放开，否则403）")
def dorm_self_select(body: CheckinBody, bedId: int = Path(...), user=Depends(require_staff)):
    return success(dorm_svc.self_select_checkin(bedId, user, body.studentId), message="已入住")


@router.post("/dorm/transfers", summary="发起调宿（原床释放/新床占用，走审批）")
def dorm_transfer_submit(body: TransferSubmit, user=Depends(require_staff)):
    return success(dorm_svc.submit_transfer(user, body.studentId, body.toBedId, body.reason or ""),
                   message="调宿已提交")


@router.post("/dorm/transfers/{transferId}/review", summary="调宿审批（辅导员→宿管→执行）")
def dorm_transfer_review(body: DormReviewBody, transferId: int = Path(...), user=Depends(require_staff)):
    return success(dorm_svc.review_transfer(transferId, user, body.action, body.reason or ""),
                   message="已处理")


@router.post("/dorm/check-tasks", summary="建宿舍检查任务")
def dorm_check_task(body: CheckTaskCreate, user=Depends(require_staff)):
    return success(dorm_svc.create_check_task(body, user), message="已创建")


@router.post("/dorm/check-tasks/{taskId}/records", summary="录检查结果（异常→风险）")
def dorm_check_record(body: CheckRecordBody, taskId: int = Path(...), user=Depends(require_staff)):
    return success(dorm_svc.submit_check_record(taskId, user, body), message="已记录")


# ═══════════ 学工归档（P6，archive）═══════════

class ArchiveBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    yearCode: Optional[str] = None
    scope: Optional[dict] = Field(default_factory=dict)


class CollectBody(BaseModel):
    studentIds: list[str] = Field(..., min_length=1)


class AdvanceBody(BaseModel):
    action: Optional[str] = Field("APPROVE")


@router.post("/archive/batches", summary="建归档批次")
def archive_batch_create(body: ArchiveBatchCreate, user=Depends(require_staff)):
    return success(archive_svc.create_batch(body, user), message="已创建")


@router.get("/archive/batches/{batchId}", summary="归档批次详情（含档案包）")
def archive_batch(batchId: int = Path(...), user=Depends(require_staff)):
    return success(archive_svc.get_batch(batchId, user))


@router.post("/archive/batches/{batchId}/collect", summary="圈定学生生成档案包")
def archive_collect(body: CollectBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(archive_svc.collect(batchId, user, body.studentIds), message="已收集")


@router.post("/archive/batches/{batchId}/advance", summary="批次流转（→归档时登记水印包）")
def archive_advance(body: AdvanceBody = AdvanceBody(), batchId: int = Path(...), user=Depends(require_staff)):
    return success(archive_svc.advance(batchId, user, body.action or "APPROVE"), message="已流转")
