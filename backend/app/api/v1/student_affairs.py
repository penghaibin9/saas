"""13A 学工中心 API（/api/v1/student-affairs/*）—— P1：首页三角色视图 + 班级/班干部骨架。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.response import success, paginate
from app.core.permissions import require_any_permission, require_permission
from app.core.security import get_current_user, require_staff  # 仅敏感 reveal 等「服务层自鉴权+落 DENY 审计」端点用粗粒度门禁，避免网关短路吞掉越权审计
from app.services import affairs_activity_service as activity_svc
from app.services import affairs_attachment_service as attach_svc
from app.services import affairs_aid_service as aid_svc
from app.services import affairs_club_service as club_svc
from app.services import affairs_counselor_eval_service as ce_svc
from app.services import affairs_league_service as league_svc
from app.services import affairs_org_service as org_svc
from app.services import affairs_archive_service as archive_svc
from app.services import affairs_class_service as class_svc
from app.services import affairs_dashboard_service as svc
from app.services import affairs_discipline_service as disc_svc
from app.services import affairs_dorm_service as dorm_svc
from app.services import affairs_funding_ext_service as fext_svc
from app.services import affairs_funding_service as funding_svc
from app.services import affairs_leave_service as leave_svc
from app.services import affairs_mental_service as mental_svc
from app.services import affairs_profile_service as profile_svc
from app.services import affairs_risk_service as risk_svc
from app.services import affairs_talk_service as talk_svc

router = APIRouter(prefix="/student-affairs", tags=["学工中心"])


@router.get("/dashboard", summary="学工首页（三角色视图，按数据范围聚合）")
def dashboard(user=Depends(require_permission("studentAffairs.dashboard.view"))):
    return success(svc.get_dashboard(user))


@router.get("/stats/cockpit", summary="学工统计驾驶舱（各域概览+下钻入口，仅聚合）")
def stats_cockpit(user=Depends(require_permission("studentAffairs.stats.view"))):
    from app.services import affairs_cockpit_service as cockpit_svc
    return success(cockpit_svc.cockpit(user))


@router.get("/classes", summary="班级列表（名称+指标，按数据范围，可筛学院/专业/年级/关键词）")
def classes(collegeId: Optional[str] = None, majorId: Optional[str] = None,
            grade: Optional[str] = None, keyword: Optional[str] = None,
            page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.class.view"))):
    items, total = class_svc.class_list(user, collegeId, majorId, grade, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/classes/{classId}/profile", summary="班级画像（人数/男女/请假/风险/困难/处分/班干部/材料聚合）")
def class_profile(classId: int = Path(...), user=Depends(require_permission("studentAffairs.class.view"))):
    return success(class_svc.class_profile(classId, user))


@router.get("/classes/{classId}/students", summary="班级学生列表（联系方式脱敏）")
def class_students(classId: int = Path(...), keyword: Optional[str] = None,
                   page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.class.view"))):
    items, total = class_svc.class_students(classId, user, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/classes/{classId}/cadres", summary="班干部列表")
def cadres(classId: int = Path(...), user=Depends(require_permission("studentAffairs.class.view"))):
    return success({"items": svc.list_cadres(classId, user)})


class CadreCreate(BaseModel):
    studentId: str = Field(..., min_length=1, description="学生 id")
    position: str = Field(..., min_length=1, description="职务编码：MONITOR/LEAGUE_SECRETARY/...")
    termCode: Optional[str] = Field(None, description="学年学期编码")


@router.post("/classes/{classId}/cadres", summary="任命班干部")
def add_cadre(body: CadreCreate, classId: int = Path(...), user=Depends(require_permission("studentAffairs.class.cadre.manage"))):
    return success(svc.add_cadre(classId, body, user), message="已任命")


@router.delete("/classes/cadres/{cadreId}", summary="免去班干部")
def remove_cadre(cadreId: int = Path(...), user=Depends(require_permission("studentAffairs.class.cadre.manage"))):
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
                    page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.class.view"))):
    items, total = class_svc.list_materials(classId, user, materialType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/classes/{classId}/materials", summary="新增班级材料（附件走文件中心 file_id）")
def add_class_material(body: MaterialCreate, classId: int = Path(...), user=Depends(require_permission("studentAffairs.class.create"))):
    return success(class_svc.add_material(classId, user, body), message="已新增")


@router.delete("/classes/materials/{materialId}", summary="作废班级材料（逻辑删除）")
def void_class_material(materialId: int = Path(...), user=Depends(require_permission("studentAffairs.class.create"))):
    return success(class_svc.void_material(materialId, user), message="已作废")


# ── 辅导员考评 ──

class PeriodCreate(BaseModel):
    periodName: str = Field(..., min_length=1, max_length=100)
    semester: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=500)


class ScoreBody(BaseModel):
    collegeScore: float = Field(..., ge=0, le=100, description="学院评分 0-100")


@router.post("/counselor-assessment/periods", summary="新建辅导员考评周期（旧入口·权限对齐正式考评）")
def counselor_period_create(body: PeriodCreate, user=Depends(require_permission("studentAffairs.counselorEval.manage"))):
    return success(class_svc.create_period(user, body.periodName, body.semester, body.remark),
                   message="已创建")


@router.get("/counselor-assessment/periods", summary="考评周期列表")
def counselor_periods(page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.counselorEval.view"))):
    items, total = class_svc.list_periods(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/counselor-assessment/periods/{periodId}/collect", summary="生成/刷新考评指标（系统抓取工作量，幂等）")
def counselor_collect(periodId: int = Path(...), user=Depends(require_permission("studentAffairs.counselorEval.manage"))):
    return success(class_svc.collect_assessments(periodId, user), message="已生成")


@router.get("/counselor-assessment/periods/{periodId}/assessments", summary="考评记录（含自动指标+评分+排名）")
def counselor_assessments(periodId: int = Path(...), user=Depends(require_permission("studentAffairs.counselorEval.view"))):
    return success({"items": class_svc.list_assessments(periodId, user)})


@router.post("/counselor-assessment/periods/{periodId}/publish", summary="发布考评周期")
def counselor_publish(periodId: int = Path(...), user=Depends(require_permission("studentAffairs.counselorEval.manage"))):
    return success(class_svc.publish_period(periodId, user), message="已发布")


@router.post("/counselor-assessment/assessments/{assessmentId}/score", summary="学院评分（综合分=自动*0.6+学院*0.4）")
def counselor_score(body: ScoreBody, assessmentId: int = Path(...), user=Depends(require_permission("studentAffairs.counselorEval.manage"))):
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
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class ExtensionBody(BaseModel):
    newEnd: str = Field(..., description="新结束时间")
    reason: Optional[str] = Field(None, max_length=500)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class ExtensionReviewBody(BaseModel):
    action: str = Field("APPROVE", description="APPROVE 续假通过 / REJECT 续假驳回")
    reason: Optional[str] = Field("", max_length=500, description="驳回原因≥5字")
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class CancelBody(BaseModel):
    proofNote: Optional[str] = Field("", max_length=500)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class ProxyCancelBody(BaseModel):
    actualReturnAt: str = Field(..., description="实际返校时间 YYYY-MM-DD[ HH:MM:SS]")
    note: Optional[str] = Field("", max_length=500)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class LeaveVersionOnlyBody(BaseModel):
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class OverdueHandleBody(BaseModel):
    handleType: str = Field(..., description="CONTACT 联系 / TO_HOME_SCHOOL 转家校 / CLOSE 处置关闭")
    note: str = Field(..., min_length=1, description="处置说明≥5字")
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class ConfirmBody(BaseModel):
    action: str = Field("CONFIRM", description="CONFIRM 销假确认 / RETURN 销假退回")
    actualReturnAt: Optional[str] = Field(None, description="确认时可校对实际返校时间")
    reason: Optional[str] = Field("", max_length=500, description="退回原因≥5字")
    note: Optional[str] = Field("", max_length=500)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


@router.post("/leave", summary="发起请假")
def leave_apply(body: LeaveApply, user=Depends(require_permission("studentAffairs.leave.create"))):
    return success(leave_svc.apply_leave(body, user), message="已提交")


@router.get("/leave/pending", summary="待审批请假（按数据范围）")
def leave_pending(page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.leave.view"))):
    items, total = leave_svc.list_pending(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/leave", summary="请假台账（全状态，按数据范围，可筛类型/班级/关键词/日期）")
def leave_ledger(status: Optional[str] = None, leaveType: Optional[str] = None,
                 classId: Optional[str] = None, keyword: Optional[str] = None,
                 dateStart: Optional[str] = None, dateEnd: Optional[str] = None,
                 followupOnly: bool = False, page: int = 1, pageSize: int = 20,
                 user=Depends(require_permission("studentAffairs.leave.view"))):
    items, total = leave_svc.list_leaves(user, status, leaveType, classId, keyword,
                                         dateStart, dateEnd, followupOnly, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/leave/stats", summary="请假统计（人数/天数/逾期未销，按班级/类型/状态下钻）")
def leave_stats(groupBy: str = "CLASS", dateStart: Optional[str] = None,
                dateEnd: Optional[str] = None, user=Depends(require_permission("studentAffairs.leave.view"))):
    return success(leave_svc.leave_stats(user, groupBy, dateStart, dateEnd))


@router.post("/leave/export", summary="请假台账导出（xlsx 水印 + 导出留痕）")
def leave_export(status: Optional[str] = None, leaveType: Optional[str] = None,
                 classId: Optional[str] = None, keyword: Optional[str] = None,
                 dateStart: Optional[str] = None, dateEnd: Optional[str] = None,
                 user=Depends(require_permission("studentAffairs.leave.export"))):
    return success(leave_svc.export_leaves(user, status, leaveType, classId, keyword,
                                           dateStart, dateEnd))


@router.get("/leave/{leaveId}", summary="请假详情（含销假/续假记录 + 审批留痕）")
def leave_detail(leaveId: int = Path(...), user=Depends(require_permission("studentAffairs.leave.view"))):
    return success(leave_svc.get_detail(leaveId, user))


@router.post("/leave/{leaveId}/approve", summary="请假审批通过（多级逐节点推进）")
def leave_approve(body: CommentBody = CommentBody(), leaveId: int = Path(...), user=Depends(require_permission("studentAffairs.leave.approve"))):
    return success(leave_svc.approve(leaveId, user, body.comment or "", body.version), message="已通过")


@router.post("/leave/{leaveId}/reject", summary="请假驳回（原因≥5字，终态）")
def leave_reject(body: ReasonBody, leaveId: int = Path(...), user=Depends(require_permission("studentAffairs.leave.approve"))):
    return success(leave_svc.reject(leaveId, user, body.reason), message="已驳回")


@router.post("/leave/{leaveId}/return", summary="请假退回重提（原因≥5字）")
def leave_return(body: ReasonBody, leaveId: int = Path(...), user=Depends(require_permission("studentAffairs.leave.approve"))):
    return success(leave_svc.return_leave(leaveId, user, body.reason), message="已退回")


@router.post("/leave/{leaveId}/resubmit", summary="退回后重新提交")
def leave_resubmit(body: LeaveVersionOnlyBody = LeaveVersionOnlyBody(), leaveId: int = Path(...),
                   user=Depends(require_permission("studentAffairs.leave.create"))):
    return success(leave_svc.resubmit(leaveId, user, body.version), message="已重新提交")


@router.post("/leave/{leaveId}/cancel", summary="发起销假")
def leave_cancel(body: CancelBody = CancelBody(), leaveId: int = Path(...), user=Depends(require_permission("studentAffairs.leave.create"))):
    return success(leave_svc.submit_cancel(leaveId, user, body.proofNote or "", body.version), message="销假已提交")


@router.post("/leave/{leaveId}/cancel-confirm", summary="销假确认/退回（辅导员）→ CLOSED 进360 / 退回 APPROVED")
def leave_cancel_confirm(body: ConfirmBody = ConfirmBody(), leaveId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.leave.cancelLeaveConfirm"))):
    r = leave_svc.confirm_cancel(leaveId, user, action=body.action,
                                 actual_return_at=body.actualReturnAt, reason=body.reason or "",
                                 note=body.note or "", expected_version=body.version)
    return success(r, message="已退回" if (body.action or "").upper() == "RETURN" else "已销假")


@router.post("/leave/{leaveId}/proxy-cancel", summary="辅导员代登记销假 → WAIT_CANCEL_LEAVE")
def leave_proxy_cancel(body: ProxyCancelBody, leaveId: int = Path(...), user=Depends(require_permission("studentAffairs.leave.cancelLeaveConfirm"))):
    return success(leave_svc.proxy_cancel(leaveId, user, body.actualReturnAt, body.note or "", body.version),
                   message="已代登记销假")


@router.post("/leave/{leaveId}/overdue-handle", summary="逾期处置登记（联系/转家校/处置关闭）")
def leave_overdue_handle(body: OverdueHandleBody, leaveId: int = Path(...), user=Depends(require_permission("studentAffairs.leave.overdue.handle"))):
    return success(leave_svc.handle_overdue(leaveId, user, body.handleType, body.note, body.version),
                   message="已登记")


@router.post("/leave/{leaveId}/extension", summary="发起续假")
def leave_extension(body: ExtensionBody, leaveId: int = Path(...), user=Depends(require_permission("studentAffairs.leave.create"))):
    return success(leave_svc.apply_extension(leaveId, user, body.newEnd, body.reason or "", body.version),
                   message="续假已提交")


@router.post("/leave/{leaveId}/extension-approve", summary="续假审批（通过/驳回）")
def leave_extension_approve(body: ExtensionReviewBody = ExtensionReviewBody(), leaveId: int = Path(...),
                            user=Depends(require_permission("studentAffairs.leave.extension.approve"))):
    r = leave_svc.approve_extension(leaveId, user, action=body.action, reason=body.reason or "",
                                    expected_version=body.version)
    return success(r, message="续假已驳回" if (body.action or "").upper() == "REJECT" else "续假已通过")


@router.post("/leave/scan-overdue", summary="逾期扫描（定时/手动触发，幂等）")
def leave_scan_overdue(user=Depends(require_permission("studentAffairs.leave.overdue.handle"))):
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
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class AidAdjustBody(BaseModel):
    targetLevel: str = Field(..., description="SPECIAL/DIFFICULT/GENERAL")
    reason: str = Field(..., min_length=1)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class AidVersionOnlyBody(BaseModel):
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class AidObjectionBody(BaseModel):
    reason: str = Field(..., min_length=5, description="异议理由≥5字")
    objectorName: Optional[str] = None


class AidObjectionReviewBody(BaseModel):
    result: str = Field(..., description="SUSTAINED异议成立/OVERRULED异议不成立")
    opinion: str = Field(..., min_length=5)


class AidRevealBody(BaseModel):
    reason: Optional[str] = Field("", description="查看完整家庭经济的原因（落 SENSITIVE 审计）")


@router.post("/aid/batches", summary="建/发布认定批次")
def aid_batch_create(body: AidBatchCreate, user=Depends(require_permission("studentAffairs.aid.batch.manage"))):
    return success(aid_svc.create_batch(body, user), message="已保存")


@router.get("/aid/batches", summary="认定批次列表")
def aid_batches(schoolYear: Optional[str] = None, status: Optional[str] = None,
                page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.aid.view"))):
    items, total = aid_svc.list_batches(user, schoolYear, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/aid/applications", summary="发起困难认定申请（含家庭经济，直达班级评议）")
def aid_apply(body: AidApplyBody, user=Depends(require_permission("studentAffairs.aid.create"))):
    return success(aid_svc.apply(body, user), message="已提交")


@router.get("/aid/applications", summary="认定申请列表（家庭经济默认脱敏）")
def aid_applications(batchId: Optional[str] = None, status: Optional[str] = None,
                     level: Optional[str] = None, page: int = 1, pageSize: int = 20,
                     user=Depends(require_permission("studentAffairs.aid.view"))):
    items, total = aid_svc.list_applications(user, batchId, status, level, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/aid/applications/{applyId}/objection", summary="对公示中申请提异议（理由≥5字）")
def aid_objection_submit(body: AidObjectionBody, applyId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.aid.view"))):
    return success(aid_svc.submit_objection(applyId, body, user), message="异议已提交")


@router.get("/aid/objections", summary="困难认定异议列表")
def aid_objections(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                   user=Depends(require_permission("studentAffairs.aid.view"))):
    items, total = aid_svc.list_objections(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/aid/objections/{objectionId}/review", summary="异议复核（成立驳回/不成立维持）")
def aid_objection_review(body: AidObjectionReviewBody, objectionId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.aid.approve"))):
    return success(aid_svc.review_objection(objectionId, body, user), message="已复核")


@router.get("/aid/difficult-students", summary="困难学生库（供助学金/绿通引用）")
def aid_difficult_students(level: Optional[str] = None, page: int = 1, pageSize: int = 50,
                           user=Depends(require_permission("studentAffairs.aid.view"))):
    items, total = aid_svc.difficult_students(user, level, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/aid/stats", summary="困难认定统计（按状态/等级聚合，仅聚合口径）")
def aid_stats(user=Depends(require_permission("studentAffairs.stats.view"))):
    return success(aid_svc.aid_stats(user))


@router.get("/aid/applications/{applyId}", summary="认定申请详情（家庭经济脱敏）")
def aid_application(applyId: int = Path(...), user=Depends(require_permission("studentAffairs.aid.view"))):
    return success(aid_svc.get_application(applyId, user))


@router.post("/aid/applications/{applyId}/review", summary="各级评审（评议/初审/复审/终审）")
def aid_review(body: AidReviewBody, applyId: int = Path(...),
               # 网关只放行"持有任一评审类权限"；具体节点是否真的授权本次操作，由服务层
               # review() -> _check_node_authority() 按当前申请所在节点二次收敛（辅导员仅
               # COUNSELOR_REVIEW 节点+本班范围，2026-07-18 甲方拍板扩权见历史欠账）。
               user=Depends(require_any_permission("studentAffairs.aid.approve", "studentAffairs.aid.counselorReview"))):
    return success(aid_svc.review(applyId, user, body.action, body.level, body.reason or ""),
                   message="已处理")


@router.post("/aid/applications/{applyId}/resubmit", summary="退回后重新提交")
def aid_resubmit(body: AidVersionOnlyBody = AidVersionOnlyBody(), applyId: int = Path(...),
                 user=Depends(require_permission("studentAffairs.aid.create"))):
    return success(aid_svc.resubmit(applyId, user, body.version), message="已重新提交")


@router.post("/aid/applications/{applyId}/publicity-confirm", summary="人工确认公示期满→通过")
def aid_publicity_confirm(body: AidVersionOnlyBody = AidVersionOnlyBody(), applyId: int = Path(...),
                          user=Depends(require_permission("studentAffairs.aid.approve"))):
    return success(aid_svc.confirm_publicity(applyId, user, body.version), message="已通过")


@router.post("/aid/scan-publicity", summary="公示期满扫描（定时/手动，幂等）")
def aid_scan_publicity(user=Depends(require_permission("studentAffairs.aid.approve"))):
    return success(aid_svc.scan_publicity())


@router.post("/aid/applications/{applyId}/adjust", summary="发起困难等级动态调整")
def aid_adjust(body: AidAdjustBody, applyId: int = Path(...), user=Depends(require_permission("studentAffairs.aid.adjust"))):
    return success(aid_svc.adjust(applyId, user, body.targetLevel, body.reason, body.version), message="调整已提交")


@router.post("/aid/applications/{applyId}/adjust-approve", summary="动态调整审批")
def aid_adjust_approve(body: AidReviewBody = None, applyId: int = Path(...), user=Depends(require_permission("studentAffairs.aid.adjust"))):
    action = body.action if body else "APPROVE"
    version = body.version if body else None
    return success(aid_svc.approve_adjust(applyId, user, action, version), message="已处理")


@router.post("/aid/applications/{applyId}/reveal", summary="查看完整家庭经济（sensitiveView+审计）")
def aid_reveal(body: AidRevealBody = AidRevealBody(), applyId: int = Path(...),
               user=Depends(require_staff)):
    # 粗粒度只挡学生；aid.sensitiveView 的授权判定与「SUCCESS/DENY 双向 SENSITIVE_VIEW 审计」由服务层
    # reveal_family_economy() 负责——网关不得在此短路，否则越权 reveal 的 DENY 审计会丢失。
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
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class FundingVersionOnlyBody(BaseModel):
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class FundingAppealBody(BaseModel):
    reason: str = Field(..., min_length=5, description="申诉理由≥5字")
    appellantName: Optional[str] = None


class FundingAppealReviewBody(BaseModel):
    result: str = Field(..., description="SUSTAINED申诉成立/OVERRULED申诉不成立")
    opinion: str = Field(..., min_length=5)


@router.post("/funding/projects", summary="建资助项目（奖学金/助学金）")
def funding_project_create(body: FundingProjectCreate, user=Depends(require_permission("studentAffairs.funding.project.manage"))):
    return success(funding_svc.create_project(body, user), message="已创建")


@router.get("/funding/projects", summary="资助项目列表")
def funding_projects(projectType: Optional[str] = None, status: Optional[str] = None,
                     page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.funding.view"))):
    items, total = funding_svc.list_projects(user, projectType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/funding/batches", summary="建/发布资助批次")
def funding_batch_create(body: FundingBatchCreate, user=Depends(require_permission("studentAffairs.funding.project.manage"))):
    return success(funding_svc.create_batch(body, user), message="已保存")


@router.get("/funding/batches", summary="资助批次列表")
def funding_batches(projectId: Optional[str] = None, status: Optional[str] = None,
                    page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.funding.view"))):
    items, total = funding_svc.list_batches(user, projectId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/funding/applications", summary="发起资助申请（含资格硬校验）")
def funding_apply(body: FundingApplyBody, user=Depends(require_permission("studentAffairs.funding.create"))):
    return success(funding_svc.apply(body, user), message="已提交")


@router.get("/funding/applications", summary="资助申请列表（金额按角色脱敏）")
def funding_applications(batchId: Optional[str] = None, projectType: Optional[str] = None,
                         status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                         user=Depends(require_permission("studentAffairs.funding.view"))):
    items, total = funding_svc.list_applications(user, batchId, projectType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/funding/applications/{applicationId}", summary="资助申请详情（含校验快照）")
def funding_application(applicationId: int = Path(...), user=Depends(require_permission("studentAffairs.funding.view"))):
    return success(funding_svc.get_application(applicationId, user))


@router.post("/funding/applications/{applicationId}/review", summary="各级评审")
def funding_review(body: FundingReviewBody, applicationId: int = Path(...), user=Depends(require_permission("studentAffairs.funding.approve"))):
    return success(funding_svc.review(applicationId, user, body.action, body.reason or "", body.version),
                   message="已处理")


@router.post("/funding/applications/{applicationId}/publicity-confirm", summary="确认公示期满→获资助")
def funding_publicity_confirm(body: FundingVersionOnlyBody = FundingVersionOnlyBody(),
                              applicationId: int = Path(...),
                              user=Depends(require_permission("studentAffairs.funding.publicity.manage"))):
    return success(funding_svc.confirm_publicity(applicationId, user, body.version), message="已通过")


@router.post("/funding/scan-publicity", summary="资助公示扫描（定时/手动，幂等）")
def funding_scan_publicity(user=Depends(require_permission("studentAffairs.funding.publicity.manage"))):
    return success(funding_svc.scan_publicity())


@router.post("/funding/applications/{applicationId}/appeal", summary="对公示中资助申请提起申诉（理由≥5字）")
def funding_appeal_submit(body: FundingAppealBody, applicationId: int = Path(...),
                          user=Depends(require_permission("studentAffairs.funding.view"))):
    return success(funding_svc.submit_appeal(applicationId, body, user), message="申诉已提交")


@router.get("/funding/appeals", summary="资助公示申诉列表")
def funding_appeals(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                    user=Depends(require_permission("studentAffairs.funding.view"))):
    items, total = funding_svc.list_appeals(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/funding/appeals/{appealId}/review", summary="资助申诉复核（成立驳回/不成立维持）")
def funding_appeal_review(body: FundingAppealReviewBody, appealId: int = Path(...),
                          user=Depends(require_permission("studentAffairs.funding.publicity.manage"))):
    return success(funding_svc.review_appeal(appealId, body, user), message="已复核")


@router.get("/funding/stats", summary="奖助统计（按状态/项目类型聚合，计数口径不含金额明细）")
def funding_stats(user=Depends(require_permission("studentAffairs.stats.view"))):
    return success(funding_svc.funding_stats(user))


# ── 奖助发放台账（C 包·发放状态/发放/异常）──
class DisbursementIssueBody(BaseModel):
    disburseNo: Optional[str] = None
    bankLast4: Optional[str] = None


@router.get("/funding/disbursements", summary="资助发放台账（金额按角色脱敏，不含卡全号）")
def funding_disbursements(batchId: Optional[int] = None, bankStatus: Optional[str] = None,
                          page: int = 1, pageSize: int = 50,
                          user=Depends(require_permission("studentAffairs.funding.view"))):
    items, total = funding_svc.list_disbursements(user, batchId, bankStatus, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/funding/batches/{batchId}/disbursements/generate", summary="按批次生成发放台账（GRANTED→PENDING，幂等）")
def funding_disbursement_generate(batchId: int = Path(...),
                                  user=Depends(require_permission("studentAffairs.funding.disburse.manage"))):
    return success(funding_svc.generate_disbursements(batchId, user), message="已生成")


@router.post("/funding/disbursements/{disbursementId}/issue", summary="标记已发放")
def funding_disbursement_issue(body: DisbursementIssueBody, disbursementId: int = Path(...),
                               user=Depends(require_permission("studentAffairs.funding.disburse.manage"))):
    return success(funding_svc.issue_disbursement(disbursementId, body, user), message="已发放")


@router.post("/funding/disbursements/{disbursementId}/fail", summary="标记发放失败（原因≥5字）")
def funding_disbursement_fail(body: ReasonBody, disbursementId: int = Path(...),
                              user=Depends(require_permission("studentAffairs.funding.disburse.manage"))):
    return success(funding_svc.fail_disbursement(disbursementId, user, body.reason or ""), message="已置失败")


@router.get("/funding/disbursements/stats", summary="发放概览（按状态计数，授权角色见已发放金额合计）")
def funding_disbursement_stats(user=Depends(require_permission("studentAffairs.stats.view"))):
    return success(funding_svc.disbursement_stats(user))


# ═══════════ 奖助扩展：勤工助学 / 助学贷款 / 减免临补（V1 解冻补建）═══════════

class WsPostBody(BaseModel):
    deptName: str = Field(..., min_length=1)
    postName: str = Field(..., min_length=1)
    salary: Optional[float] = None
    headcount: Optional[int] = None
    requirement: Optional[str] = None


class WsApplyBody(BaseModel):
    studentId: int = Field(...)


class WsActionBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT/ONBOARD/TERMINATE")
    reason: Optional[str] = ""


class LoanBody(BaseModel):
    studentId: int = Field(...)
    loanType: Optional[str] = Field("ORIGIN", description="ORIGIN/CAMPUS")
    bankName: Optional[str] = None
    bankLast4: Optional[str] = None
    yearCode: Optional[str] = None
    amount: Optional[float] = None
    remark: Optional[str] = None


class FeeBody(BaseModel):
    studentId: int = Field(...)
    itemType: Optional[str] = Field("REDUCTION", description="REDUCTION/TEMP_AID")
    amount: Optional[float] = None
    reason: str = Field(..., min_length=5)


class FeeReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    opinion: Optional[str] = ""


# —— 勤工助学 ——
@router.get("/work-study/posts", summary="勤工助学岗位列表")
def ws_posts(status: Optional[str] = None, user=Depends(require_permission("studentAffairs.funding.view"))):
    return success({"items": fext_svc.list_posts(user, status)})


@router.post("/work-study/posts", summary="发布勤工岗位")
def ws_post_create(body: WsPostBody, user=Depends(require_permission("studentAffairs.funding.workstudy.manage"))):
    return success(fext_svc.create_post(body, user), message="已发布")


@router.get("/work-study/records", summary="勤工上岗记录（数据范围）")
def ws_records(postId: Optional[int] = None, status: Optional[str] = None,
               user=Depends(require_permission("studentAffairs.funding.view"))):
    return success({"items": fext_svc.list_ws_records(user, postId, status)})


@router.post("/work-study/posts/{postId}/apply", summary="学生申请勤工岗位（代录）")
def ws_apply(body: WsApplyBody, postId: int = Path(...),
             user=Depends(require_permission("studentAffairs.funding.workstudy.manage"))):
    return success(fext_svc.apply_work_study(postId, body, user), message="已申请")


@router.post("/work-study/records/{recordId}/action", summary="勤工流转（录用/拒绝/上岗/终止）")
def ws_action(body: WsActionBody, recordId: int = Path(...),
              user=Depends(require_permission("studentAffairs.funding.workstudy.manage"))):
    return success(fext_svc.act_work_study(recordId, body.action, user, body.reason or ""), message="已处理")


class WsMonthlyBody(BaseModel):
    monthCode: str = Field(..., min_length=1, description="考核月，如 2025-10")
    workHours: Optional[float] = None
    rating: Optional[str] = Field("PASS", description="GOOD/PASS/FAIL")
    subsidyAmount: Optional[float] = None
    remark: Optional[str] = None


@router.get("/work-study/records/{recordId}/monthly", summary="勤工月度考核明细")
def ws_monthly_list(recordId: int = Path(...),
                    user=Depends(require_permission("studentAffairs.funding.view"))):
    return success({"items": fext_svc.list_monthly(recordId, user)})


@router.post("/work-study/records/{recordId}/monthly", summary="录勤工月度考核（累计补贴）")
def ws_monthly_add(body: WsMonthlyBody, recordId: int = Path(...),
                   user=Depends(require_permission("studentAffairs.funding.workstudy.manage"))):
    return success(fext_svc.add_monthly(recordId, body, user), message="已录入")


# —— 助学贷款 ——
@router.get("/loans", summary="助学贷款台账（金额脱敏，不含卡全号）")
def loans(status: Optional[str] = None, user=Depends(require_permission("studentAffairs.funding.view"))):
    return success({"items": fext_svc.list_loans(user, status)})


@router.post("/loans", summary="登记助学贷款")
def loan_register(body: LoanBody, user=Depends(require_permission("studentAffairs.funding.loan.manage"))):
    return success(fext_svc.register_loan(body, user), message="已登记")


@router.post("/loans/{loanId}/advance", summary="贷款推进（登记→回执→核对→确认）")
def loan_advance(loanId: int = Path(...),
                 user=Depends(require_permission("studentAffairs.funding.loan.manage"))):
    return success(fext_svc.advance_loan(loanId, user), message="已推进")


# —— 减免与临时补助 ——
@router.get("/fee-reductions", summary="减免/临补台账（数据范围）")
def fee_reductions(itemType: Optional[str] = None, status: Optional[str] = None,
                   user=Depends(require_permission("studentAffairs.funding.view"))):
    return success({"items": fext_svc.list_reductions(user, itemType, status)})


@router.post("/fee-reductions", summary="申请学费减免/临时补助（理由≥5字）")
def fee_submit(body: FeeBody, user=Depends(require_permission("studentAffairs.funding.reduction.manage"))):
    return success(fext_svc.submit_reduction(body, user), message="已提交")


@router.post("/fee-reductions/{feeId}/review", summary="减免/临补审核（批准/驳回）")
def fee_review(body: FeeReviewBody, feeId: int = Path(...),
               user=Depends(require_permission("studentAffairs.funding.reduction.manage"))):
    return success(fext_svc.review_reduction(feeId, body, user), message="已处理")


@router.post("/fee-reductions/{feeId}/issue", summary="减免/临补发放")
def fee_issue(feeId: int = Path(...),
              user=Depends(require_permission("studentAffairs.funding.reduction.manage"))):
    return success(fext_svc.issue_reduction(feeId, user), message="已发放")


# ═══════════ 违纪处分（P4，discipline 全套）═══════════

class DisciplineRegister(BaseModel):
    studentId: str = Field(..., min_length=1)
    discType: str = Field(..., description="WARNING/SERIOUS_WARNING/DEMERIT/PROBATION/EXPEL")
    reason: str = Field(..., min_length=1, description="违纪事实≥5字")
    docNo: Optional[str] = None


class DiscReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT/RETURN")
    reason: Optional[str] = Field("", max_length=500)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class DiscRemoveBody(BaseModel):
    reason: str = Field(..., min_length=1, description="解除理由≥5字")
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class DiscVersionOnlyBody(BaseModel):
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


@router.post("/discipline/cases", summary="登记违纪处分")
def discipline_register(body: DisciplineRegister, user=Depends(require_permission("studentAffairs.discipline.create"))):
    return success(disc_svc.register(body, user), message="已登记")


@router.get("/discipline/cases", summary="处分列表（学生端仅数量，此为教师侧明细）")
def discipline_cases(status: Optional[str] = None, discType: Optional[str] = None,
                     page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.discipline.view"))):
    items, total = disc_svc.list_cases(user, status, discType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/discipline/reconcile", summary="处分投影一致性对账")
def discipline_reconcile(user=Depends(require_permission("studentAffairs.discipline.view"))):
    return success(disc_svc.projection_reconcile())


@router.get("/discipline/stats", summary="违纪处分统计（按类型/状态聚合 + 投影对账）")
def discipline_stats(user=Depends(require_permission("studentAffairs.stats.view"))):
    return success(disc_svc.discipline_stats(user))


@router.get("/discipline/cases/{caseId}", summary="处分详情")
def discipline_case(caseId: int = Path(...), user=Depends(require_permission("studentAffairs.discipline.view"))):
    return success(disc_svc.get_case(caseId, user))


@router.post("/discipline/cases/{caseId}/submit", summary="提交学院初审")
def discipline_submit(body: DiscVersionOnlyBody = DiscVersionOnlyBody(), caseId: int = Path(...),
                      user=Depends(require_permission("studentAffairs.discipline.create"))):
    return success(disc_svc.submit(caseId, user, body.version), message="已提交")


@router.post("/discipline/cases/{caseId}/cancel", summary="撤销登记")
def discipline_cancel(body: DiscVersionOnlyBody = DiscVersionOnlyBody(), caseId: int = Path(...),
                      user=Depends(require_permission("studentAffairs.discipline.create"))):
    return success(disc_svc.cancel(caseId, user, body.version), message="已撤销")


@router.post("/discipline/cases/{caseId}/review", summary="处分审批（学院初审/学工处复核/校级）")
def discipline_review(body: DiscReviewBody, caseId: int = Path(...), user=Depends(require_permission("studentAffairs.discipline.approve"))):
    return success(disc_svc.review(caseId, user, body.action, body.reason or "", body.version), message="已处理")


@router.post("/discipline/cases/{caseId}/remove", summary="发起处分解除申请")
def discipline_remove(body: DiscRemoveBody, caseId: int = Path(...), user=Depends(require_permission("studentAffairs.discipline.remove.create"))):
    return success(disc_svc.submit_remove(caseId, user, body.reason, body.version), message="解除已提交")


@router.post("/discipline/cases/{caseId}/remove-review", summary="处分解除审批（辅→院→处）")
def discipline_remove_review(body: DiscReviewBody, caseId: int = Path(...), user=Depends(require_permission("studentAffairs.discipline.remove.approve"))):
    return success(disc_svc.review_remove(caseId, user, body.action, body.reason or "", body.version), message="已处理")


# ── 决定送达 + 申诉复核（C 包）──
class DiscDeliverBody(BaseModel):
    method: str = Field(..., description="DIRECT/MAIL/PUBLIC/LEAVE")
    remark: Optional[str] = None
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class DiscAppealSubmitBody(BaseModel):
    reason: str = Field(..., min_length=5, description="申诉理由≥5字")


class DiscAppealReviewBody(BaseModel):
    result: str = Field(..., description="UPHELD/REVISED/REVOKED")
    opinion: str = Field(..., min_length=5, description="复核意见≥5字")
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


@router.post("/discipline/cases/{caseId}/deliver", summary="登记决定书送达（仅已生效）")
def discipline_deliver(body: DiscDeliverBody, caseId: int = Path(...),
                       user=Depends(require_permission("studentAffairs.discipline.deliver"))):
    return success(disc_svc.deliver_case(caseId, body, user), message="已登记送达")


@router.post("/discipline/cases/{caseId}/appeal", summary="提起处分申诉（已生效后）")
def discipline_appeal_submit(body: DiscAppealSubmitBody, caseId: int = Path(...),
                             user=Depends(require_permission("studentAffairs.discipline.appeal.create"))):
    return success(disc_svc.submit_appeal(caseId, body, user), message="申诉已提交")


@router.get("/discipline/appeals", summary="处分申诉列表")
def discipline_appeals(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                       user=Depends(require_permission("studentAffairs.discipline.view"))):
    items, total = disc_svc.list_appeals(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/discipline/appeals/{appealId}/review", summary="申诉复核（维持/变更/撤销）")
def discipline_appeal_review(body: DiscAppealReviewBody, appealId: int = Path(...),
                             user=Depends(require_permission("studentAffairs.discipline.appeal.review"))):
    return success(disc_svc.review_appeal(appealId, body, user), message="已复核")


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
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class RiskContentBody(BaseModel):
    content: Optional[str] = Field("", max_length=1000)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class RiskTransferBody(BaseModel):
    newOwnerId: str = Field(..., min_length=1)
    reason: Optional[str] = Field("", max_length=500)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class RiskReasonBody(BaseModel):
    reason: Optional[str] = Field("", max_length=500)
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


class RiskCloseBody(BaseModel):
    conclusion: str = Field(..., min_length=1, description="关闭结论≥5字")
    version: Optional[int] = Field(None, description="乐观锁：传则校验，不传不阻断（兼容旧前端）")


@router.post("/risk/records", summary="建风险记录（多来源，去重）")
def risk_create(body: RiskCreate, user=Depends(require_permission("studentAffairs.risk.create"))):
    return success(risk_svc.create_risk(body, user), message="已建单")


@router.get("/risk/records", summary="风险列表（心理来源仅摘要，明细遮蔽）")
def risk_records(source: Optional[str] = None, status: Optional[str] = None,
                 riskLevel: Optional[str] = None, page: int = 1, pageSize: int = 20,
                 user=Depends(require_permission("studentAffairs.risk.view"))):
    items, total = risk_svc.list_risks(user, source, status, riskLevel, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/risk/records/{riskId}", summary="风险详情（心理明细须填原因+SENSITIVE_VIEW）")
def risk_record(riskId: int = Path(...), reason: Optional[str] = None,
                user=Depends(require_permission("studentAffairs.risk.view"))):
    return success(risk_svc.get_risk(riskId, user, reason))


@router.get("/risk/owner-candidates", summary="可分派的风险责任人（在职+持学工风险处置角色）")
def risk_owner_candidates(keyword: Optional[str] = None,
                          user=Depends(require_permission("studentAffairs.risk.assign"))):
    return success({"items": risk_svc.list_owner_candidates(keyword)})


@router.post("/risk/records/{riskId}/assign", summary="分派责任人")
def risk_assign(body: RiskAssignBody, riskId: int = Path(...),
                user=Depends(require_permission("studentAffairs.risk.assign"))):
    return success(risk_svc.assign(riskId, user, body.ownerId, body.version), message="已分派")


@router.post("/risk/records/{riskId}/process", summary="处置（首条→PROCESSING）")
def risk_process(body: RiskContentBody, riskId: int = Path(...),
                 user=Depends(require_permission("studentAffairs.risk.handle"))):
    return success(risk_svc.process(riskId, user, body.content or "", body.version), message="已处置")


@router.post("/risk/records/{riskId}/follow", summary="转持续跟进")
def risk_follow(body: RiskContentBody = RiskContentBody(), riskId: int = Path(...),
                user=Depends(require_permission("studentAffairs.risk.handle"))):
    return success(risk_svc.follow(riskId, user, body.content or "", body.version), message="已转跟进")


@router.post("/risk/records/{riskId}/transfer", summary="转办（换责任人）")
def risk_transfer(body: RiskTransferBody, riskId: int = Path(...),
                  user=Depends(require_permission("studentAffairs.risk.transfer"))):
    return success(risk_svc.transfer(riskId, user, body.newOwnerId, body.reason or "", body.version),
                   message="已转办")


@router.post("/risk/records/{riskId}/escalate", summary="升级")
def risk_escalate(body: RiskReasonBody = RiskReasonBody(), riskId: int = Path(...),
                  user=Depends(require_permission("studentAffairs.risk.escalate"))):
    return success(risk_svc.escalate(riskId, user, body.reason or "", body.version), message="已升级")


@router.post("/risk/records/{riskId}/takeover", summary="上级接管")
def risk_takeover(body: RiskContentBody = RiskContentBody(), riskId: int = Path(...),
                  user=Depends(require_permission("studentAffairs.risk.handle"))):
    return success(risk_svc.takeover(riskId, user, body.content or "", body.version), message="已接管")


@router.post("/risk/records/{riskId}/close", summary="关闭（结论≥5字，进360）")
def risk_close(body: RiskCloseBody, riskId: int = Path(...),
               user=Depends(require_permission("studentAffairs.risk.close"))):
    return success(risk_svc.close(riskId, user, body.conclusion, body.version), message="已关闭")


@router.post("/risk/records/{riskId}/reopen", summary="复发重开")
def risk_reopen(body: RiskReasonBody = RiskReasonBody(), riskId: int = Path(...),
                user=Depends(require_permission("studentAffairs.risk.reopen"))):
    return success(risk_svc.reopen(riskId, user, body.reason or "", body.version), message="已重开")


@router.post("/risk/scan-timeout", summary="风险超时扫描（分派/升级，幂等）")
def risk_scan_timeout(user=Depends(require_permission("studentAffairs.risk.handle"))):
    return success(risk_svc.scan_timeout())


# ═══════════ 心理关注（强敏感·PSY_STUDENT 逐生授权·危机接风险中枢）═══════════

class PsyReferralCreate(BaseModel):
    studentId: str = Field(..., description="学生ID")
    level: str = Field("FOCUS", description="GENERAL/FOCUS/CRISIS（人工登记）")
    channel: Optional[str] = Field(None, description="转介去向：校医院/专业机构/家长/校内咨询")
    reasonSummary: str = Field(..., min_length=1, description="转介事由摘要≥5字（非诊断结论）")
    note: Optional[str] = Field(None, description="涉密明细")


class PsyContentBody(BaseModel):
    content: str = Field("", description="回访/升级说明")


class PsyCloseBody(BaseModel):
    conclusion: str = Field(..., min_length=1, description="关闭结论≥5字")


@router.get("/mental/list", summary="心理关注名单（PSY_STUDENT 数据范围，列表仅摘要）")
def mental_list(level: Optional[str] = None, page: int = 1, pageSize: int = 20,
                user=Depends(require_permission("studentAffairs.risk.psyDetail.view"))):
    items, total = mental_svc.list_attention(user, level=level, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/mental/referrals/{refId}", summary="转介详情（心理明细须原因+SENSITIVE_VIEW）")
def mental_referral(refId: int = Path(...), reason: Optional[str] = None,
                    user=Depends(require_permission("studentAffairs.risk.psyDetail.view"))):
    return success(mental_svc.get_referral(user, refId, reason))


@router.get("/mental/students/{studentId}/summary", summary="心理预警摘要（仅需关注标记，无明细）")
def mental_summary(studentId: int = Path(...),
                   user=Depends(require_permission("studentAffairs.risk.view"))):
    return success(mental_svc.student_summary(user, studentId))


@router.post("/mental/referrals", summary="登记心理转介（人工，无自动诊断）")
def mental_refer(body: PsyReferralCreate,
                 user=Depends(require_permission("studentAffairs.mental.manage"))):
    return success(mental_svc.create_referral(user, body), message="已转介")


@router.post("/mental/referrals/{refId}/follow", summary="回访（→FOLLOWING）")
def mental_follow(body: PsyContentBody, refId: int = Path(...),
                  user=Depends(require_permission("studentAffairs.mental.manage"))):
    return success(mental_svc.follow_referral(user, refId, body.content or ""), message="已回访")


@router.post("/mental/referrals/{refId}/escalate", summary="危机升级（接风险中枢，幂等）")
def mental_escalate(body: PsyContentBody = PsyContentBody(), refId: int = Path(...),
                    user=Depends(require_permission("studentAffairs.mental.manage"))):
    return success(mental_svc.escalate_crisis(user, refId, body.content or ""), message="已升级危机")


@router.post("/mental/referrals/{refId}/close", summary="关闭转介（结论≥5字）")
def mental_close(body: PsyCloseBody, refId: int = Path(...),
                 user=Depends(require_permission("studentAffairs.mental.manage"))):
    return success(mental_svc.close_referral(user, refId, body.conclusion), message="已关闭")


@router.get("/mental/stats", summary="心理统计（仅聚合，禁个体明细）")
def mental_stats(user=Depends(require_permission("studentAffairs.stats.view"))):
    return success(mental_svc.stats(user))


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
def student_profile(studentId: int = Path(...), user=Depends(require_permission("studentAffairs.student.view"))):
    return success(profile_svc.get_profile(studentId, user))


@router.get("/students/{studentId}/timeline", summary="成长时间线（360，各域进360事件倒序）")
def student_timeline(studentId: int = Path(...), eventType: Optional[str] = None,
                     page: int = 1, pageSize: int = 20, user=Depends(require_permission("studentAffairs.student.view"))):
    items, total = profile_svc.get_timeline(studentId, user, eventType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/talks", summary="谈话列表（管理侧默认摘要，心理类按权限）")
def talks(talkType: Optional[str] = None, status: Optional[str] = None,
          studentId: Optional[str] = None, page: int = 1, pageSize: int = 20,
          user=Depends(require_permission("studentAffairs.talk.view"))):
    items, total = talk_svc.list_talks(user, talkType, status, studentId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/talks", summary="建谈话计划（批量圈定学生）")
def talk_create(body: TalkCreate, user=Depends(require_permission("studentAffairs.talk.create"))):
    return success(talk_svc.create_talk(body, user), message="已创建")


@router.get("/talks/stats", summary="谈话工作量统计（完成率）")
def talk_stats(groupBy: str = "TYPE", user=Depends(require_permission("studentAffairs.talk.view"))):
    return success(talk_svc.talk_stats(user, groupBy))


@router.get("/talks/{talkId}", summary="谈话详情（心理类全文按权限）")
def talk_detail(talkId: int = Path(...), user=Depends(require_permission("studentAffairs.talk.view"))):
    return success(talk_svc.get_talk(talkId, user))


@router.post("/talks/{talkId}/record", summary="填写谈话记录（→COMPLETED，进360）")
def talk_record(body: TalkRecordBody, talkId: int = Path(...), user=Depends(require_permission("studentAffairs.talk.create"))):
    return success(talk_svc.record_talk(talkId, user, body.content, body.result or "", body.needFollowUp),
                   message="已记录")


@router.post("/talks/{talkId}/follow-up", summary="跟进/办结/转风险/转家校")
def talk_follow(body: TalkFollowBody, talkId: int = Path(...), user=Depends(require_permission("studentAffairs.talk.create"))):
    return success(talk_svc.follow_up(talkId, user, body.action, body.content or ""), message="已处理")


@router.get("/students/{studentId}/family-contacts", summary="家校联系记录列表")
def family_contacts(studentId: int = Path(...), page: int = 1, pageSize: int = 20,
                    user=Depends(require_permission("studentAffairs.homeSchool.view"))):
    items, total = talk_svc.list_contacts(studentId, user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/students/{studentId}/family-contacts", summary="登记家校联系（完整号码必填原因+审计）")
def family_contact_create(body: ContactCreate, studentId: int = Path(...), user=Depends(require_permission("studentAffairs.homeSchool.record.create"))):
    return success(talk_svc.create_contact(studentId, user, body), message="已登记")


class ReceiptBody(BaseModel):
    note: Optional[str] = ""


@router.get("/family-contacts", summary="家校联系记录（全局，数据范围，可按回执状态筛）")
def family_contacts_all(receiptStatus: Optional[str] = None, page: int = 1, pageSize: int = 50,
                        user=Depends(require_permission("studentAffairs.homeSchool.view"))):
    items, total = talk_svc.list_all_contacts(user, receiptStatus, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/family-contacts/{contactId}/receipt", summary="登记家长回执（待回执→已回执）")
def family_contact_receipt(body: ReceiptBody, contactId: int = Path(...),
                           user=Depends(require_permission("studentAffairs.homeSchool.record.create"))):
    return success(talk_svc.mark_receipt(contactId, user, body.note or ""), message="回执已登记")


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
    studentId: Optional[str] = Field(None, description="涉事学生（夜不归宿必填；异常→风险绑真实学生，SEC-4）")


@router.post("/dorm/buildings", summary="新建楼栋（带层数/房数/床位则一键铺满）")
def dorm_building_create(body: BuildingCreate, user=Depends(require_permission("studentAffairs.dorm.resource.manage"))):
    return success(dorm_svc.create_building(body, user), message="已创建")


@router.get("/dorm/buildings", summary="楼栋列表（宿管仅本人负责楼栋；选床级联1；gender 过滤）")
def dorm_buildings(gender: Optional[str] = None, page: int = 1, pageSize: int = 50,
                   user=Depends(require_permission("studentAffairs.dorm.view"))):
    items, total = dorm_svc.list_buildings(user, gender, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/dorm/buildings/{buildingId}/generate", summary="铺房+床（层数×每层房数×每间床位）")
def dorm_generate(body: GenerateBody, buildingId: int = Path(...),
                  user=Depends(require_permission("studentAffairs.dorm.resource.manage"))):
    return success(dorm_svc.generate_layout(buildingId, user, body.floors, body.roomsPerFloor,
                                            body.bedsPerRoom), message="已铺床位")


@router.get("/dorm/buildings/{buildingId}/rooms", summary="房间列表（选床级联2；floor 过滤，带空床数）")
def dorm_rooms(buildingId: int = Path(...), floor: Optional[int] = None, page: int = 1,
               pageSize: int = 100, user=Depends(require_permission("studentAffairs.dorm.view"))):
    items, total = dorm_svc.list_rooms(buildingId, user, floor, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/dorm/rooms/{roomId}/beds", summary="床位列表（选床级联3；标空/已住）")
def dorm_beds(roomId: int = Path(...), user=Depends(require_permission("studentAffairs.dorm.view"))):
    return success({"items": dorm_svc.list_beds(roomId, user)})


@router.get("/dorm/occupancy", summary="宿舍入住率统计")
def dorm_occupancy(user=Depends(require_permission("studentAffairs.dorm.view"))):
    return success(dorm_svc.occupancy_stats(user))


@router.post("/dorm/beds/{bedId}/checkin", summary="学生入住某床（回写我的宿舍）")
def dorm_checkin(body: CheckinBody, bedId: int = Path(...),
                 user=Depends(require_permission("studentAffairs.dorm.allocation.manage"))):
    return success(dorm_svc.checkin(bedId, user, body.studentId), message="已入住")


@router.post("/dorm/beds/{bedId}/checkout", summary="退宿（释放床位）")
def dorm_checkout(bedId: int = Path(...),
                  user=Depends(require_permission("studentAffairs.dorm.allocation.manage"))):
    return success(dorm_svc.checkout(bedId, user), message="已退宿")


class DormConfigBody(BaseModel):
    enabled: bool = Field(..., description="是否放开学生自选宿舍（true=学生自选，false=辅导员分配）")


@router.get("/dorm/config", summary="宿舍分配模式（学生自选是否放开）")
def dorm_config(user=Depends(require_permission("studentAffairs.dorm.view"))):
    return success(dorm_svc.get_dorm_config(user))


@router.put("/dorm/config/self-select", summary="学校开/关学生自选宿舍")
def dorm_set_self_select(body: DormConfigBody,
                         user=Depends(require_permission("studentAffairs.dorm.allocation.manage"))):
    return success(dorm_svc.set_self_select(user, body.enabled),
                   message=("已放开学生自选" if body.enabled else "已切换为辅导员分配"))


@router.post("/dorm/beds/{bedId}/self-select", summary="学生自选床位入住（需学校放开，否则403）")
def dorm_self_select(body: CheckinBody, bedId: int = Path(...),
                     user=Depends(require_permission("studentAffairs.dorm.allocation.manage"))):
    return success(dorm_svc.self_select_checkin(bedId, user, body.studentId), message="已入住")


@router.post("/dorm/transfers", summary="发起调宿（原床释放/新床占用，走审批）")
def dorm_transfer_submit(body: TransferSubmit,
                         user=Depends(require_permission("studentAffairs.dorm.transfer.create"))):
    return success(dorm_svc.submit_transfer(user, body.studentId, body.toBedId, body.reason or ""),
                   message="调宿已提交")


@router.get("/dorm/transfers", summary="调宿申请列表（宿管仅本人楼栋）")
def dorm_transfers(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                   user=Depends(require_permission("studentAffairs.dorm.view"))):
    items, total = dorm_svc.list_transfers(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/dorm/transfers/{transferId}/review", summary="调宿审批（辅导员→宿管→执行）")
def dorm_transfer_review(body: DormReviewBody, transferId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.dorm.transfer.approve"))):
    return success(dorm_svc.review_transfer(transferId, user, body.action, body.reason or ""),
                   message="已处理")


@router.post("/dorm/check-tasks", summary="建宿舍检查任务")
def dorm_check_task(body: CheckTaskCreate,
                    user=Depends(require_permission("studentAffairs.dorm.inspection.manage"))):
    return success(dorm_svc.create_check_task(body, user), message="已创建")


@router.get("/dorm/check-tasks", summary="宿舍检查任务列表（宿管仅本人楼栋）")
def dorm_check_tasks(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                     user=Depends(require_permission("studentAffairs.dorm.view"))):
    items, total = dorm_svc.list_check_tasks(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/dorm/check-tasks/{taskId}/records", summary="录检查结果（异常→风险，须绑真实学生）")
def dorm_check_record(body: CheckRecordBody, taskId: int = Path(...),
                      user=Depends(require_permission("studentAffairs.dorm.inspection.manage"))):
    return success(dorm_svc.submit_check_record(taskId, user, body), message="已记录")


@router.get("/dorm/check-tasks/{taskId}/records", summary="某检查任务的记录列表")
def dorm_check_records(taskId: int = Path(...), page: int = 1, pageSize: int = 100,
                       user=Depends(require_permission("studentAffairs.dorm.view"))):
    items, total = dorm_svc.list_check_records(taskId, user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/dorm/exceptions", summary="宿舍异常列表（含夜不归宿；宿管仅本人楼栋）")
def dorm_exceptions(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                    user=Depends(require_permission("studentAffairs.dorm.view"))):
    items, total = dorm_svc.list_exceptions(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


class DormExcHandleBody(BaseModel):
    reason: str = Field("", description="处置说明≥5字")


@router.post("/dorm/exceptions/{exceptionId}/handle", summary="处理宿舍异常（说明≥5字）")
def dorm_exception_handle(exceptionId: int = Path(...), body: DormExcHandleBody = DormExcHandleBody(),
                          user=Depends(require_permission("studentAffairs.dorm.exception.handle"))):
    return success(dorm_svc.handle_exception(exceptionId, user, body.reason or ""), message="已处理")


# ═══════════ 学工归档（P6，archive）═══════════

class ArchiveBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    yearCode: Optional[str] = None
    scope: Optional[dict] = Field(default_factory=dict)


class CollectBody(BaseModel):
    studentIds: list[str] = Field(..., min_length=1)


class AdvanceBody(BaseModel):
    action: Optional[str] = Field("APPROVE")


@router.get("/archive/batches", summary="归档批次列表")
def archive_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                    user=Depends(require_permission("studentAffairs.archive.view"))):
    items, total = archive_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/archive/batches", summary="建归档批次")
def archive_batch_create(body: ArchiveBatchCreate, user=Depends(require_permission("studentAffairs.archive.batch.manage"))):
    return success(archive_svc.create_batch(body, user), message="已创建")


@router.get("/archive/batches/{batchId}", summary="归档批次详情（含档案包）")
def archive_batch(batchId: int = Path(...), user=Depends(require_permission("studentAffairs.archive.view"))):
    return success(archive_svc.get_batch(batchId, user))


@router.post("/archive/batches/{batchId}/collect", summary="圈定学生生成档案包")
def archive_collect(body: CollectBody, batchId: int = Path(...), user=Depends(require_permission("studentAffairs.archive.batch.manage"))):
    return success(archive_svc.collect(batchId, user, body.studentIds), message="已收集")


@router.post("/archive/batches/{batchId}/advance", summary="批次流转（→归档时登记水印包）")
def archive_advance(body: AdvanceBody = AdvanceBody(), batchId: int = Path(...), user=Depends(require_permission("studentAffairs.archive.batch.manage"))):
    return success(archive_svc.advance(batchId, user, body.action or "APPROVE"), message="已流转")


# ═══════════ 学生活动与第二课堂（D 包波次1 · /activities /second-class）═══════════

class ActivityBody(BaseModel):
    activityName: str = Field(..., min_length=1)
    activityType: Optional[str] = Field("ACTIVITY")
    scopeType: Optional[str] = None
    scopeRef: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    startAt: Optional[str] = None
    endAt: Optional[str] = None
    enrollDeadline: Optional[str] = None
    quota: Optional[int] = None
    creditType: Optional[str] = None
    creditValue: Optional[float] = None
    categoryCode: Optional[str] = None


class ActivityPublishBody(BaseModel):
    action: str = Field("PUBLISH")
    reason: Optional[str] = ""


class ActivityTransitionBody(BaseModel):
    action: str = Field(..., description="ENROLL_CLOSE/START/FINISH")


class ReasonBody(BaseModel):
    reason: Optional[str] = ""


class CategoryBody(BaseModel):
    categoryCode: str = Field(..., min_length=1)
    categoryName: str = Field(..., min_length=1)
    creditType: Optional[str] = None
    weight: Optional[float] = Field(None, gt=0, description="类目加权系数（成绩单加权汇总；默认1）")
    description: Optional[str] = None
    sortOrder: Optional[int] = 0


class VolunteerBody(BaseModel):
    studentId: int = Field(..., description="学生主档 id")
    serviceName: str = Field(..., min_length=1)
    hours: float = Field(..., gt=0, description="认定时长(小时)")
    orgName: Optional[str] = None
    serviceDate: Optional[str] = None


class ClubBody(BaseModel):
    clubName: str = Field(..., min_length=1)
    clubType: Optional[str] = Field("INTEREST")
    collegeId: Optional[int] = None
    advisorName: Optional[str] = None
    presidentStudentId: Optional[int] = None
    founderStudentId: Optional[int] = None


class ClubReviewBody(BaseModel):
    action: str = Field("APPROVE", description="APPROVE/REJECT")
    reason: Optional[str] = ""


class ClubMemberBody(BaseModel):
    studentId: int = Field(...)
    role: Optional[str] = Field("MEMBER")


class ClubAnnualReviewBody(BaseModel):
    reviewYear: str = Field(..., min_length=1)
    result: Optional[str] = Field("PASS", description="PASS/CONDITIONAL/FAIL")
    activityCount: Optional[int] = None
    comment: Optional[str] = None


class OrgBody(BaseModel):
    orgName: str = Field(..., min_length=1)
    orgType: Optional[str] = Field("STUDENT_UNION")
    level: Optional[str] = Field("SCHOOL", description="SCHOOL/COLLEGE")
    collegeId: Optional[int] = None
    advisorName: Optional[str] = None


class OrgPositionBody(BaseModel):
    studentId: int = Field(...)
    position: str = Field(..., min_length=1)
    termCode: Optional[str] = None


class LeagueDevBody(BaseModel):
    studentId: int = Field(...)
    devType: Optional[str] = Field("PARTY", description="PARTY/LEAGUE")
    branchName: Optional[str] = None


class LeagueStageBody(BaseModel):
    toStage: str = Field(..., description="APPLICANT/ACTIVIST/DEVELOPMENT_TARGET/PROBATIONARY/FULL_MEMBER")
    materialFileId: Optional[int] = None
    remark: Optional[str] = None


@router.get("/activities", summary="活动列表（type/status 过滤）")
def activities(activityType: Optional[str] = None, status: Optional[str] = None,
               page: int = 1, pageSize: int = 20,
               user=Depends(require_permission("studentAffairs.activity.view"))):
    items, total = activity_svc.list_activities(user, activityType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/activities", summary="建活动（草稿）")
def activity_create(body: ActivityBody, user=Depends(require_permission("studentAffairs.activity.create"))):
    return success(activity_svc.create_activity(body, user), message="已创建")


@router.put("/activities/{activityId}", summary="编辑活动（仅草稿）")
def activity_update(body: ActivityBody, activityId: int = Path(...),
                    user=Depends(require_permission("studentAffairs.activity.create"))):
    return success(activity_svc.update_activity(activityId, body, user), message="已保存")


@router.post("/activities/{activityId}/publish", summary="发布/取消活动")
def activity_publish(body: ActivityPublishBody, activityId: int = Path(...),
                     user=Depends(require_permission("studentAffairs.activity.publish"))):
    return success(activity_svc.publish_activity(activityId, user, body.action, body.reason or ""))


@router.post("/activities/{activityId}/transition", summary="流转（报名截止/开始/结束）")
def activity_transition(body: ActivityTransitionBody, activityId: int = Path(...),
                        user=Depends(require_permission("studentAffairs.activity.publish"))):
    return success(activity_svc.transition_activity(activityId, user, body.action))


@router.get("/activities/{activityId}/participants", summary="活动名单")
def activity_participants(activityId: int = Path(...),
                          user=Depends(require_permission("studentAffairs.activity.view"))):
    return success({"items": activity_svc.list_participants(activityId, user)})


@router.post("/activities/{activityId}/confirm", summary="确认名单+生成学时/积分→进360")
def activity_confirm(activityId: int = Path(...),
                     user=Depends(require_permission("studentAffairs.activity.confirm"))):
    return success(activity_svc.confirm_activity(activityId, user), message="已确认")


@router.post("/activities/{activityId}/unconfirm", summary="撤销确认（原因≥5字）")
def activity_unconfirm(body: ReasonBody, activityId: int = Path(...),
                       user=Depends(require_permission("studentAffairs.activity.confirm"))):
    return success(activity_svc.unconfirm_activity(activityId, user, body.reason or ""), message="已撤销")


@router.post("/activities/{activityId}/archive", summary="归档活动")
def activity_archive(activityId: int = Path(...),
                     user=Depends(require_permission("studentAffairs.activity.confirm"))):
    return success(activity_svc.archive_activity(activityId, user), message="已归档")


@router.get("/second-class/ledger", summary="二课积分台账（数据范围过滤）")
def second_class_ledger(creditType: Optional[str] = None, page: int = 1, pageSize: int = 50,
                        user=Depends(require_permission("studentAffairs.stats.view"))):
    items, total = activity_svc.credit_ledger(user, creditType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/second-class/students/{studentId}/report", summary="个人第二课堂成绩单")
def second_class_report(studentId: int = Path(...),
                        user=Depends(require_permission("studentAffairs.stats.view"))):
    return success(activity_svc.student_report(studentId, user))


@router.get("/second-class/categories", summary="二课积分类目列表")
def second_class_categories(user=Depends(require_permission("studentAffairs.activity.view"))):
    return success({"items": activity_svc.list_categories(user)})


@router.post("/second-class/categories", summary="建二课积分类目")
def second_class_category_create(body: CategoryBody,
                                 user=Depends(require_permission("studentAffairs.config.manage"))):
    return success(activity_svc.create_category(body, user), message="已创建")


@router.get("/activity-stats", summary="活动与第二课堂统计（仅聚合）")
def activity_stats(user=Depends(require_permission("studentAffairs.stats.view"))):
    return success(activity_svc.activity_stats(user))


# ── 第二课堂积分申诉（D 包）──
class CreditAppealBody(BaseModel):
    studentId: int = Field(...)
    appealType: Optional[str] = Field("MISSING", description="MISSING缺记/WRONG记错")
    claimCreditType: Optional[str] = Field("SECOND_CLASS")
    claimValue: Optional[float] = None
    activityId: Optional[int] = None
    reason: str = Field(..., min_length=5)


class CreditAppealReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    opinion: Optional[str] = ""


@router.get("/second-class/appeals", summary="第二课堂积分申诉列表")
def credit_appeals(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                   user=Depends(require_permission("studentAffairs.activity.view"))):
    items, total = activity_svc.list_credit_appeals(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/second-class/appeals", summary="提交积分申诉（缺记/记错，理由≥5字）")
def credit_appeal_submit(body: CreditAppealBody,
                         user=Depends(require_permission("studentAffairs.activity.create"))):
    return success(activity_svc.submit_credit_appeal(body, user), message="申诉已提交")


@router.post("/second-class/appeals/{appealId}/review", summary="积分申诉审核（通过补记/驳回）")
def credit_appeal_review(body: CreditAppealReviewBody, appealId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.activity.confirm"))):
    return success(activity_svc.review_credit_appeal(appealId, body, user), message="已审核")


# ═══════════ 辅导员考评（D 包·指标/评分/发布/申诉）═══════════

class EvalIndicatorBody(BaseModel):
    name: str = Field(..., min_length=1)
    category: Optional[str] = None
    weight: Optional[float] = None
    maxScore: Optional[float] = None
    sortOrder: Optional[int] = 0


class EvalUpsertBody(BaseModel):
    periodCode: str = Field(..., min_length=1)
    counselorKey: str = Field(..., min_length=1)
    counselorName: Optional[str] = None
    scores: Optional[dict] = Field(default_factory=dict)
    remark: Optional[str] = None


class EvalAppealBody(BaseModel):
    reason: str = Field(..., min_length=5)


class EvalAppealReviewBody(BaseModel):
    result: str = Field(..., description="UPHELD/ADJUSTED")
    opinion: str = Field(..., min_length=5)
    scores: Optional[dict] = None


@router.get("/counselor-eval/indicators", summary="辅导员考评指标列表")
def ce_indicators(status: Optional[str] = None,
                  user=Depends(require_permission("studentAffairs.counselorEval.view"))):
    return success({"items": ce_svc.list_indicators(user, status)})


@router.post("/counselor-eval/indicators", summary="建考评指标")
def ce_indicator_create(body: EvalIndicatorBody,
                        user=Depends(require_permission("studentAffairs.counselorEval.manage"))):
    return success(ce_svc.create_indicator(body, user), message="已创建")


@router.get("/counselor-eval/evals", summary="辅导员考评记录（按总分降序）")
def ce_evals(periodCode: Optional[str] = None, status: Optional[str] = None, page: int = 1, pageSize: int = 50,
             user=Depends(require_permission("studentAffairs.counselorEval.view"))):
    items, total = ce_svc.list_evals(user, periodCode, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/counselor-eval/evals", summary="录/改考评评分（发布前）")
def ce_eval_upsert(body: EvalUpsertBody,
                   user=Depends(require_permission("studentAffairs.counselorEval.manage"))):
    return success(ce_svc.upsert_eval(body, user), message="已保存")


@router.post("/counselor-eval/evals/{evalId}/publish", summary="发布考评")
def ce_eval_publish(evalId: int = Path(...),
                    user=Depends(require_permission("studentAffairs.counselorEval.manage"))):
    return success(ce_svc.publish_eval(evalId, user), message="已发布")


@router.post("/counselor-eval/evals/{evalId}/appeal", summary="辅导员对考评申诉")
def ce_eval_appeal(body: EvalAppealBody, evalId: int = Path(...),
                   user=Depends(require_permission("studentAffairs.counselorEval.appeal.create"))):
    return success(ce_svc.submit_eval_appeal(evalId, body, user), message="申诉已提交")


@router.post("/counselor-eval/evals/{evalId}/appeal-review", summary="考评申诉复核（维持/调整）")
def ce_eval_appeal_review(body: EvalAppealReviewBody, evalId: int = Path(...),
                          user=Depends(require_permission("studentAffairs.counselorEval.manage"))):
    return success(ce_svc.review_eval_appeal(evalId, body, user), message="已复核")


@router.get("/volunteer/records", summary="志愿服务时长补录列表（数据范围）")
def volunteer_records(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                      user=Depends(require_permission("studentAffairs.activity.view"))):
    items, total = activity_svc.list_volunteer(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/volunteer/records", summary="补录志愿时长（待认定）")
def volunteer_create(body: VolunteerBody,
                     user=Depends(require_permission("studentAffairs.activity.create"))):
    return success(activity_svc.create_volunteer(body, user), message="已提交")


@router.post("/volunteer/records/{recordId}/confirm", summary="认定志愿时长→生成学分")
def volunteer_confirm(recordId: int = Path(...),
                      user=Depends(require_permission("studentAffairs.activity.confirm"))):
    return success(activity_svc.confirm_volunteer(recordId, user), message="已认定")


@router.post("/volunteer/records/{recordId}/reject", summary="驳回志愿时长补录（原因≥5字）")
def volunteer_reject(body: ReasonBody, recordId: int = Path(...),
                     user=Depends(require_permission("studentAffairs.activity.confirm"))):
    return success(activity_svc.reject_volunteer(recordId, user, body.reason or ""), message="已驳回")


# ── 社团管理（05 卡）──
@router.get("/clubs", summary="社团列表（status/type 过滤）")
def clubs(status: Optional[str] = None, clubType: Optional[str] = None, page: int = 1, pageSize: int = 50,
          user=Depends(require_permission("studentAffairs.club.view"))):
    items, total = club_svc.list_clubs(user, status, clubType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/clubs", summary="建社团（待审批）")
def club_create(body: ClubBody, user=Depends(require_permission("studentAffairs.club.manage"))):
    return success(club_svc.create_club(body, user), message="已提交")


@router.post("/clubs/{clubId}/review", summary="社团审批（通过/驳回）")
def club_review(body: ClubReviewBody, clubId: int = Path(...),
                user=Depends(require_permission("studentAffairs.club.manage"))):
    return success(club_svc.review_club(clubId, user, body.action, body.reason or ""), message="已处理")


@router.post("/clubs/{clubId}/disband", summary="注销社团（原因≥5字）")
def club_disband(body: ReasonBody, clubId: int = Path(...),
                 user=Depends(require_permission("studentAffairs.club.manage"))):
    return success(club_svc.disband_club(clubId, user, body.reason or ""), message="已注销")


@router.get("/clubs/{clubId}/members", summary="社团成员列表")
def club_members(clubId: int = Path(...),
                 user=Depends(require_permission("studentAffairs.club.view"))):
    return success({"items": club_svc.list_members(clubId, user)})


@router.post("/clubs/{clubId}/members", summary="增补社团成员/任职")
def club_member_add(body: ClubMemberBody, clubId: int = Path(...),
                    user=Depends(require_permission("studentAffairs.club.manage"))):
    return success(club_svc.add_member(clubId, body, user), message="已加入")


@router.post("/clubs/members/{memberId}/remove", summary="成员退社")
def club_member_remove(memberId: int = Path(...),
                       user=Depends(require_permission("studentAffairs.club.manage"))):
    return success(club_svc.remove_member(memberId, user), message="已退社")


@router.get("/clubs/{clubId}/annual-reviews", summary="社团年审记录")
def club_annual_reviews(clubId: int = Path(...),
                        user=Depends(require_permission("studentAffairs.club.view"))):
    return success({"items": club_svc.list_annual_reviews(clubId, user)})


@router.post("/clubs/{clubId}/annual-reviews", summary="社团年审（一社一年一条）")
def club_annual_review_create(body: ClubAnnualReviewBody, clubId: int = Path(...),
                              user=Depends(require_permission("studentAffairs.club.manage"))):
    return success(club_svc.annual_review(clubId, body, user), message="年审已记录")


# ── 学生干部与组织（06 卡）──
@router.get("/organizations", summary="学生组织列表（level/status 过滤）")
def organizations(level: Optional[str] = None, status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                  user=Depends(require_permission("studentAffairs.org.view"))):
    items, total = org_svc.list_orgs(user, level, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/organizations", summary="建学生组织")
def organization_create(body: OrgBody, user=Depends(require_permission("studentAffairs.org.manage"))):
    return success(org_svc.create_org(body, user), message="已创建")


@router.get("/organizations/{orgId}/positions", summary="组织在任成员")
def organization_positions(orgId: int = Path(...),
                           user=Depends(require_permission("studentAffairs.org.view"))):
    return success({"items": org_svc.list_positions(orgId, user)})


@router.post("/organizations/{orgId}/positions", summary="任命组织成员")
def organization_appoint(body: OrgPositionBody, orgId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.org.manage"))):
    return success(org_svc.appoint(orgId, body, user), message="已任命")


@router.post("/organizations/positions/{positionId}/dismiss", summary="卸任组织成员")
def organization_dismiss(positionId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.org.manage"))):
    return success(org_svc.dismiss(positionId, user), message="已卸任")


@router.get("/students/{studentId}/cadre-resume", summary="学生干部履历（组织任职+班级班干部）")
def student_cadre_resume(studentId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.org.view"))):
    return success({"items": org_svc.student_resume(studentId, user)})


# ── 党团建设（07 卡；发展阶段台账，材料脱敏，时限/审批/政治面貌回写见历史欠账）──
@router.get("/party-league/dev", summary="党团发展台账列表（数据范围，不含材料明文）")
def league_dev_list(devType: Optional[str] = None, stage: Optional[str] = None, status: Optional[str] = None,
                    page: int = 1, pageSize: int = 50,
                    user=Depends(require_permission("studentAffairs.league.view"))):
    items, total = league_svc.list_dev(user, devType, stage, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/party-league/dev", summary="建党团发展台账（起始入党/团申请人）")
def league_dev_create(body: LeagueDevBody, user=Depends(require_permission("studentAffairs.league.manage"))):
    return success(league_svc.create_dev(body, user), message="已建档")


@router.post("/party-league/dev/{devId}/advance", summary="推进发展阶段（记流转+材料脱敏）")
def league_dev_advance(body: LeagueStageBody, devId: int = Path(...),
                       user=Depends(require_permission("studentAffairs.league.manage"))):
    return success(league_svc.advance_stage(devId, body, user), message="已推进")


@router.post("/party-league/dev/{devId}/terminate", summary="终止发展（原因≥5字）")
def league_dev_terminate(body: ReasonBody, devId: int = Path(...),
                         user=Depends(require_permission("studentAffairs.league.manage"))):
    return success(league_svc.terminate_dev(devId, user, body.reason or ""), message="已终止")


@router.get("/party-league/dev/{devId}/stages", summary="发展阶段时间线（材料仅标记有无）")
def league_dev_stages(devId: int = Path(...),
                      user=Depends(require_permission("studentAffairs.league.view"))):
    return success({"items": league_svc.list_stages(devId, user)})


# ═══════════ 统一业务附件（违纪/送达/申诉/党团/减免贷款回执/家校 材料·授权下载+审计）═══════════
# 上传字节复用 POST /api/v1/files/upload（真实落盘 + t_file_object），本节只做「关联/列表/授权下载」。

class AttachmentLinkBody(BaseModel):
    bizType: str = Field(..., description="DISCIPLINE/DISCIPLINE_APPEAL/LEAGUE/CLUB/FUNDING/REDUCTION/LOAN/HOME_SCHOOL")
    bizId: int = Field(..., description="业务记录 id")
    fileId: str = Field(..., min_length=1, description="POST /files/upload 返回的 fileId")
    note: Optional[str] = None


@router.post("/attachments", summary="关联业务材料附件（需对应 biz 管理权限；file 先经 /files/upload 上传）")
def attachment_link(body: AttachmentLinkBody, user=Depends(get_current_user)):
    return success(attach_svc.link_attachment(body.bizType, body.bizId, body.fileId, body.note, user),
                   message="已关联")


@router.get("/attachments", summary="业务材料附件列表（脱敏：仅名称+id；需对应 biz 查看权限）")
def attachment_list(bizType: str, bizId: int, user=Depends(get_current_user)):
    return success({"items": attach_svc.list_attachments(bizType, bizId, user)})


@router.get("/attachments/{attachmentId}/download", summary="授权下载业务材料（require_permission 按 biz + SENSITIVE_EXPORT 审计）")
def attachment_download(attachmentId: int = Path(...), user=Depends(get_current_user)):
    from fastapi.responses import FileResponse

    from app.core.exceptions import not_found
    resolved = attach_svc.download_attachment(attachmentId, user)
    if not resolved:
        raise not_found("文件不存在或已丢失")
    path, filename = resolved
    return FileResponse(str(path), filename=filename)
