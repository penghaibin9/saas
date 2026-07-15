"""13B 教务中心 API（/api/v1/academic-affairs/*）—— P1：首页 + 学年学期/校历/节次 + 学籍名册 + 入学注册。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Path, UploadFile
from pydantic import BaseModel, Field

from app.core.exceptions import AppException
from app.core.permissions import require_any_permission, require_permission
from app.core.response import paginate, success
from app.core.security import get_current_user, require_staff
from app.schemas.excel import ExcelErrorRows, ExcelImportRows


def _require_student(user: dict = Depends(get_current_user)) -> dict:
    """学生本人端点守卫：仅 userType=STUDENT（对齐项目约定——学生不进 PC 管理端权限点，走本人端点）。"""
    if (user.get("userType") or "").strip().upper() != "STUDENT":
        raise AppException("NO_PERMISSION", "仅学生本人可访问选课自助端点", http_status=403)
    return user
from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_svc
from app.modules.academic_affairs.services import academic_affairs_change_service as change_svc
from app.modules.academic_affairs.services import academic_affairs_course_service as course_svc
from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_svc
from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad_svc
from app.modules.academic_affairs.services import academic_affairs_org_service as org_svc
from app.modules.academic_affairs.services import academic_affairs_program_service as prog_svc
from app.modules.academic_affairs.services import academic_affairs_resource_service as resource_svc
from app.modules.academic_affairs.services import academic_affairs_schedule_change_service as sched_change_svc
from app.modules.academic_affairs.services import academic_affairs_schedule_service as sched_svc
from app.modules.academic_affairs.services import academic_affairs_scheduling_service as scheduling_svc
from app.modules.academic_affairs.services import academic_affairs_warning_service as warn_svc
from app.modules.academic_affairs.services import academic_affairs_evaluation_service as evaluation_svc
from app.modules.academic_affairs.services import academic_affairs_quality_service as quality_svc
from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup_svc
from app.modules.academic_affairs.services import academic_affairs_textbook_service as textbook_svc
from app.modules.academic_affairs.services import academic_affairs_selection_service as selection_svc
from app.modules.academic_affairs.services import academic_affairs_service as svc
from app.modules.academic_affairs.services import academic_affairs_stats_service as stats_svc
from app.modules.academic_affairs.services import academic_affairs_task_service as task_svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])


@router.get("/dashboard", summary="教务首页（当前学期 + 模块卡）")
def dashboard(user=Depends(require_staff)):
    return success(svc.dashboard(user))


@router.get("/dashboard/reminders", summary="教务看板提醒聚合（成绩提交进度/考试安排/学籍异动/学业预警/毕业资格预警/教务待办）")
def dashboard_reminders(user=Depends(require_staff)):
    return success(svc.dashboard_reminders(user))


# ── 学年学期 ──
class TermCreate(BaseModel):
    yearCode: str = Field(..., min_length=1, description="学年 如 2026-2027")
    termNo: int = Field(..., ge=1, le=2)
    termName: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    teachingWeeks: Optional[int] = None
    examWeekStart: Optional[int] = None


@router.post("/terms", summary="新建学年学期")
def term_create(body: TermCreate, user=Depends(require_staff)):
    return success(svc.create_term(body, user), message="已创建")


@router.get("/terms", summary="学期列表")
def terms(status: Optional[str] = None, page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = svc.list_terms(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/terms/current", summary="当前学期")
def term_current(user=Depends(require_staff)):
    return success(svc.current_term(user))


@router.post("/terms/{termId}/publish", summary="发布学期（设为当前，幂等）")
def term_publish(termId: int = Path(...), user=Depends(require_staff)):
    return success(svc.publish_term(termId, user), message="已发布")


class CalendarEventBody(BaseModel):
    eventType: str = Field("TEACHING", description="TEACHING/EXAM/INTERNSHIP/HOLIDAY/SWAP")
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    swapToDate: Optional[str] = None
    remark: Optional[str] = None


@router.post("/terms/{termId}/calendar", summary="添加校历事件")
def calendar_add(body: CalendarEventBody, termId: int = Path(...), user=Depends(require_staff)):
    return success(svc.add_calendar_event(termId, user, body), message="已添加")


@router.get("/terms/{termId}/calendar", summary="校历事件列表")
def calendar_list(termId: int = Path(...), user=Depends(require_staff)):
    return success({"items": svc.list_calendar(termId, user)})


# ── 作息节次 ──
class TimeSlotCreate(BaseModel):
    slotNo: int = Field(..., ge=1)
    slotName: Optional[str] = None
    startTime: Optional[str] = Field(None, description="HH:MM")
    endTime: Optional[str] = None


@router.post("/time-slots", summary="新建作息节次")
def time_slot_create(body: TimeSlotCreate, user=Depends(require_staff)):
    return success(svc.create_time_slot(body, user), message="已创建")


@router.get("/time-slots", summary="作息节次列表")
def time_slots(user=Depends(require_staff)):
    return success({"items": svc.list_time_slots(user)})


# ── 学籍名册 ──
@router.get("/roster", summary="学籍名册（只读主档，脱敏）")
def roster(keyword: Optional[str] = None, status: Optional[str] = None,
           page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = svc.roster(user, keyword, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ── 学籍档案 / 学籍状态 / 学籍异动记录（只读展示，复用 status-changes）/ 学籍导入导出（Tier1 R2）──
# 权限：view=档案详情+状态总览；viewSensitive=证件号完整查看（服务层二次鉴权+SUCCESS/DENY 双向审计）；
# import=批量建档；export=名册导出。静态子路由（status-summary/export/import/*）必须声明在 /roster/{studentId} 之前，
# 否则会被路径参数捕获（对齐 gd-students 路由注释的既有约定）。
_ROSTER_VIEW = "academicAffairs.roster.view"
_ROSTER_VIEW_SENSITIVE = "academicAffairs.roster.viewSensitive"
_ROSTER_IMPORT = "academicAffairs.roster.import"
_ROSTER_EXPORT = "academicAffairs.roster.export"


@router.get("/roster/status-summary", summary="学籍状态总览（13 态分布 + 在籍统计 + 近30天异动数）")
def roster_status_summary(user=Depends(require_permission(_ROSTER_VIEW))):
    return success(svc.roster_status_summary(user))


class RosterExportBody(BaseModel):
    purpose: str = Field(..., min_length=5, description="导出用途（≥5 字，必填，写审计）")
    keyword: Optional[str] = None
    status: Optional[str] = None


@router.post("/roster/export", summary="导出学籍名册 xlsx（脱敏水印+审计，同步下载）")
def roster_export(body: RosterExportBody, user=Depends(require_permission(_ROSTER_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content = svc.export_roster_xlsx(user, body.purpose, body.keyword, body.status)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=roster_ledger.xlsx"})


@router.get("/roster/import/template", summary="学籍导入·下载 Excel 模板(.xlsx)")
def roster_import_template(user=Depends(require_permission(_ROSTER_IMPORT))):
    import io

    from fastapi.responses import StreamingResponse
    data = svc.roster_import_template_bytes()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=roster_import_template.xlsx"})


@router.post("/roster/import/dry-run", summary="学籍导入·预校验（粘贴行/高级，不写库）")
def roster_import_dry_run(body: ExcelImportRows, user=Depends(require_permission(_ROSTER_IMPORT))):
    return success(svc.roster_import_dry_run(body.rows))


@router.post("/roster/import/xlsx", summary="学籍导入·上传 Excel 解析+预校验（不写库）")
async def roster_import_xlsx(file: UploadFile = File(...), user=Depends(require_permission(_ROSTER_IMPORT))):
    content = await file.read()
    rows = svc.roster_import_read(content)
    dry = svc.roster_import_dry_run(rows)
    return success({"rows": rows, **dry})


@router.post("/roster/import/errors-xlsx", summary="学籍导入·下载错误行 Excel")
def roster_import_errors_xlsx(body: ExcelErrorRows, user=Depends(require_permission(_ROSTER_IMPORT))):
    return success(svc.roster_import_errors_pack(body.rows, [e.model_dump() for e in body.errors]))


@router.post("/roster/import/confirm", summary="学籍导入·确认（整批事务，须预校验全通过）")
def roster_import_confirm(body: ExcelImportRows, user=Depends(require_permission(_ROSTER_IMPORT))):
    result = svc.roster_import_confirm(body.rows)
    return success(result, message="导入完成")


@router.get("/roster/{studentId}", summary="学籍档案详情（主档+组织名称+学籍状态历史，数据范围收敛）")
def roster_detail(studentId: int = Path(...), user=Depends(require_permission(_ROSTER_VIEW))):
    return success(svc.roster_detail(studentId, user))


class RosterRevealBody(BaseModel):
    reason: str = Field(..., min_length=5, description="查看理由（≥5 字，必填，写审计）")


@router.post("/roster/{studentId}/reveal", summary="查看完整证件号（sensitiveView+强制审计）")
def roster_reveal(body: RosterRevealBody, studentId: int = Path(...), user=Depends(require_staff)):
    # 粗粒度只挡未登录/非教职工；academicAffairs.roster.viewSensitive 的授权判定与
    # 「SUCCESS/DENY 双向 SENSITIVE_VIEW 审计」由服务层负责，网关不得在此短路（否则越权 DENY 审计会丢失）。
    return success(svc.reveal_roster_sensitive(studentId, user, body.reason))


# ── 入学/学年注册 ──
class RegBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    registerType: str = Field("ENROLL", description="ENROLL 入学 / ANNUAL 学年")
    termId: Optional[str] = None
    windowStart: Optional[str] = None
    windowEnd: Optional[str] = None
    open: bool = Field(False)


class RegisterBody(BaseModel):
    studentId: str = Field(..., min_length=1)


@router.post("/registration-batches", summary="新建注册批次")
def reg_batch_create(body: RegBatchCreate, user=Depends(require_staff)):
    return success(svc.create_registration_batch(body, user), message="已创建")


@router.get("/registration-batches", summary="注册批次列表（registerType 可收窄为入学/学年注册视图）")
def reg_batches(status: Optional[str] = None, registerType: Optional[str] = None,
                page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = svc.list_registration_batches(user, status, page, pageSize, registerType)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/register", summary="学生注册（经 change_student_status 单一入口）")
def register(body: RegisterBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(svc.register_student(batchId, user, body.studentId), message="注册成功")


@router.get("/registration-batches/{batchId}/registrations", summary="注册记录列表")
def registrations(batchId: int = Path(...), page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = svc.list_registrations(batchId, user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ── 注册资格核验（Tier1 R1）──
_REG_ELIGIBILITY_VIEW = "academicAffairs.registration.eligibility.view"
_REG_ELIGIBILITY_VERIFY = "academicAffairs.registration.eligibility.verify"


class EligibilityVerifyBody(BaseModel):
    result: str = Field(..., description="ELIGIBLE / INELIGIBLE")
    note: Optional[str] = Field(None, description="核验意见；INELIGIBLE 必填")
    exceptionType: Optional[str] = Field(None, description="INELIGIBLE 时的异常类型")


@router.get("/registration-batches/{batchId}/eligibility", summary="注册资格核验候选名单")
def reg_eligibility_list(batchId: int = Path(...), status: Optional[str] = None, keyword: Optional[str] = None,
                         page: int = 1, pageSize: int = 20, user=Depends(require_permission(_REG_ELIGIBILITY_VIEW))):
    items, total = svc.list_registration_eligibility(batchId, user, status, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/eligibility/{studentId}/verify", summary="核验单个学生注册资格")
def reg_eligibility_verify(body: EligibilityVerifyBody, batchId: int = Path(...), studentId: str = Path(...),
                           user=Depends(require_permission(_REG_ELIGIBILITY_VERIFY))):
    return success(svc.verify_registration_eligibility(batchId, user, studentId, body.result, body.note,
                                                        body.exceptionType), message="已核验")


# ── 未注册学生（Tier1 R1）──
_REG_UNREG_VIEW = "academicAffairs.registration.unregistered.view"
_REG_UNREG_SCAN = "academicAffairs.registration.unregistered.scan"
_REG_UNREG_EXPORT = "academicAffairs.registration.unregistered.export"


@router.get("/registration/unregistered", summary="未注册学生名单（已判定 UNREGISTERED + 逾期待扫描）")
def reg_unregistered_list(batchId: Optional[int] = None, page: int = 1, pageSize: int = 20,
                          user=Depends(require_permission(_REG_UNREG_VIEW))):
    items, total = svc.list_unregistered_students(user, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/scan-unregistered", summary="扫描批次逾期未注册（仅教务处）")
def reg_scan_unregistered(batchId: int = Path(...), user=Depends(require_permission(_REG_UNREG_SCAN))):
    return success(svc.scan_unregistered(batchId, user), message="扫描完成")


class UnregisteredExportBody(BaseModel):
    batchId: Optional[int] = None
    purpose: str = Field(..., min_length=5, description="导出用途（≥5 字，必填，写审计）")


@router.post("/registration/unregistered/export", summary="导出未注册学生名单 xlsx（水印+审计，同步下载）")
def reg_unregistered_export(body: UnregisteredExportBody, user=Depends(require_permission(_REG_UNREG_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content = svc.export_unregistered_xlsx(user, body.batchId, body.purpose)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=unregistered_students.xlsx"})


# ── 暂缓注册（Tier1 R1）──
_REG_DEFERRAL_VIEW = "academicAffairs.registration.deferral.view"
_REG_DEFERRAL_APPLY = "academicAffairs.registration.deferral.apply"
_REG_DEFERRAL_APPROVE = "academicAffairs.registration.deferral.approve"


class DeferralApplyBody(BaseModel):
    studentId: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=2)
    requestedUntil: Optional[str] = None


@router.post("/registration-batches/{batchId}/deferrals", summary="提交暂缓注册申请")
def reg_deferral_apply(body: DeferralApplyBody, batchId: int = Path(...),
                       user=Depends(require_permission(_REG_DEFERRAL_APPLY))):
    return success(svc.apply_registration_deferral(batchId, user, body.studentId, body.reason,
                                                    body.requestedUntil), message="已提交")


@router.get("/registration/deferrals", summary="暂缓注册申请列表")
def reg_deferral_list(batchId: Optional[int] = None, status: Optional[str] = None,
                      page: int = 1, pageSize: int = 20, user=Depends(require_permission(_REG_DEFERRAL_VIEW))):
    items, total = svc.list_registration_deferrals(user, batchId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


class DeferralReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE / REJECT")
    note: Optional[str] = Field(None, description="REJECT 时必填")


@router.post("/registration/deferrals/{deferralId}/review", summary="审批暂缓注册申请")
def reg_deferral_review(body: DeferralReviewBody, deferralId: int = Path(...),
                        user=Depends(require_permission(_REG_DEFERRAL_APPROVE))):
    return success(svc.review_registration_deferral(deferralId, user, body.action, body.note), message="已处理")


# ── 注册异常（Tier1 R1）──
_REG_EXCEPTION_VIEW = "academicAffairs.registration.exception.view"
_REG_EXCEPTION_CREATE = "academicAffairs.registration.exception.create"
_REG_EXCEPTION_RESOLVE = "academicAffairs.registration.exception.resolve"


class ExceptionCreateBody(BaseModel):
    studentId: str = Field(..., min_length=1)
    exceptionType: str = Field(..., description="IDENTITY_MISMATCH/UNPAID/MATERIAL_MISSING/OTHER")
    description: Optional[str] = Field(None, description="OTHER 时必填")


@router.post("/registration-batches/{batchId}/exceptions", summary="标记注册异常")
def reg_exception_create(body: ExceptionCreateBody, batchId: int = Path(...),
                         user=Depends(require_permission(_REG_EXCEPTION_CREATE))):
    return success(svc.create_registration_exception(batchId, user, body.studentId, body.exceptionType,
                                                      body.description), message="已标记异常")


@router.get("/registration/exceptions", summary="注册异常列表")
def reg_exception_list(batchId: Optional[int] = None, status: Optional[str] = None,
                       page: int = 1, pageSize: int = 20, user=Depends(require_permission(_REG_EXCEPTION_VIEW))):
    items, total = svc.list_registration_exceptions(user, batchId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


class ExceptionResolveBody(BaseModel):
    note: str = Field(..., min_length=1, description="处理说明")


@router.post("/registration/exceptions/{exceptionId}/resolve", summary="处理并解除注册异常")
def reg_exception_resolve(body: ExceptionResolveBody, exceptionId: int = Path(...),
                          user=Depends(require_permission(_REG_EXCEPTION_RESOLVE))):
    return success(svc.resolve_registration_exception(exceptionId, user, body.note), message="已处理")


# ═══════════ 学籍异动（P2 台账/发起 + Tier1 R1 分类申请入口/审批/生效/统计，休学/复学/退学/转专业/留级）═══════════
# 权限：apply=发起（教务处/学院教务代录，学院教务限本院）；view=只读兜底；
# counselorReview/collegeReview/officeReview=按审批节点收敛（辅导员限本班/学院教务限本院/教务处终审全校）。
_SC_APPLY = "academicAffairs.statusChange.apply"
_SC_VIEW = "academicAffairs.statusChange.view"
_SC_COUNSELOR = "academicAffairs.statusChange.counselorReview"
_SC_COLLEGE = "academicAffairs.statusChange.collegeReview"
_SC_OFFICE = "academicAffairs.statusChange.officeReview"
_SC_LIST_VIEW = require_any_permission(_SC_VIEW, _SC_COUNSELOR, _SC_COLLEGE, _SC_OFFICE)
_SC_REVIEW_ANY = require_any_permission(_SC_COUNSELOR, _SC_COLLEGE, _SC_OFFICE)


class StatusChangeSubmit(BaseModel):
    studentId: str = Field(..., min_length=1)
    changeType: str = Field(..., description="SUSPEND/RESUME/WITHDRAW/RETAIN/TRANSFER_MAJOR")
    reason: Optional[str] = Field("", max_length=500)
    toCollegeId: Optional[str] = None
    toMajorId: Optional[str] = None
    toClassId: Optional[str] = None


class AaReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT/RETURN")
    reason: Optional[str] = Field("", max_length=500)


@router.post("/status-changes", summary="发起学籍异动（含休学/复学/退学/转专业分类申请入口，changeType 区分）")
def status_change_submit(body: StatusChangeSubmit, user=Depends(require_permission(_SC_APPLY))):
    return success(change_svc.submit(body, user), message="异动已提交")


@router.get("/status-changes", summary="学籍异动列表（台账/分类申请记录/异动生效均复用，范围过滤）")
def status_changes(changeType: Optional[str] = None, status: Optional[str] = None,
                   studentId: Optional[str] = None, page: int = 1, pageSize: int = 20,
                   user=Depends(_SC_LIST_VIEW)):
    items, total = change_svc.list_changes(user, changeType, status, studentId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/status-changes/stats", summary="学籍异动统计（按类型/状态/在途节点聚合，范围过滤）")
def status_change_stats(termCode: Optional[str] = None, user=Depends(require_permission(_SC_VIEW))):
    return success(change_svc.stats(user, termCode))


@router.get("/status-changes/{changeId}", summary="异动详情")
def status_change_detail(changeId: int = Path(...), user=Depends(_SC_LIST_VIEW)):
    return success(change_svc.get_change(changeId, user))


@router.post("/status-changes/{changeId}/review", summary="异动审批（多节点，终审经单一入口生效；节点授权见 service）")
def status_change_review(body: AaReviewBody, changeId: int = Path(...), user=Depends(_SC_REVIEW_ANY)):
    return success(change_svc.review(changeId, user, body.action, body.reason or ""), message="已处理")


# ═══════════ 培养方案（P2 编制骨架，审批发布 P3）═══════════

class ProgramCreate(BaseModel):
    programName: str = Field(..., min_length=1)
    majorId: Optional[str] = None
    gradeYear: Optional[str] = None
    totalCredits: Optional[int] = None
    requirement: Optional[dict] = Field(default_factory=dict)


class ProgramUpdate(BaseModel):
    programName: Optional[str] = None
    totalCredits: Optional[int] = None
    requirement: Optional[dict] = None


class ProgramCourseBody(BaseModel):
    courseId: Optional[str] = None
    courseName: str = Field(..., min_length=1)
    openTermNo: Optional[int] = None
    module: Optional[str] = None
    credit: Optional[int] = None


_PROG_VIEW = require_permission("academicAffairs.program.view")
_PROG_MANAGE = require_permission("academicAffairs.program.manage")
_PROG_SUBMIT = require_permission("academicAffairs.program.submit")
_PROG_REVIEW = require_permission("academicAffairs.program.review")
_PROG_PUBLISH = require_permission("academicAffairs.program.publish")


@router.post("/programs", summary="新建培养方案")
def program_create(body: ProgramCreate, user=Depends(_PROG_MANAGE)):
    return success(prog_svc.create_program(body, user), message="已创建")


@router.get("/programs", summary="培养方案列表（statusIn 支持逗号分隔多状态，供审核/发布工作台筛选）")
def programs(majorId: Optional[str] = None, status: Optional[str] = None, statusIn: Optional[str] = None,
             page: int = 1, pageSize: int = 20, user=Depends(_PROG_VIEW)):
    items, total = prog_svc.list_programs(user, majorId, status, page, pageSize, statusIn)
    return success(paginate(items, total, page, pageSize))


@router.get("/programs/{programId}", summary="方案详情（含课程明细+学分差额）")
def program_detail(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success(prog_svc.get_program(programId, user))


@router.put("/programs/{programId}", summary="编辑方案（编制态）")
def program_update(body: ProgramUpdate, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.update_program(programId, user, body), message="已保存")


@router.post("/programs/{programId}/courses", summary="方案增课程明细")
def program_add_course(body: ProgramCourseBody, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.add_course(programId, user, body), message="已添加")


class ProgramCourseUpdate(BaseModel):
    courseName: Optional[str] = None
    openTermNo: Optional[int] = None
    module: Optional[str] = None
    credit: Optional[int] = None


@router.put("/programs/courses/{programCourseId}", summary="方案课程模块：编辑课程明细（编制态）")
def program_course_update(body: ProgramCourseUpdate, programCourseId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.update_course(programCourseId, user, body), message="已保存")


@router.delete("/programs/courses/{programCourseId}", summary="方案课程模块：删除课程明细（编制态）")
def program_course_delete(programCourseId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.delete_course(programCourseId, user), message="已删除")


@router.post("/programs/{programId}/submit", summary="提交方案审核（发布前校验学分达标）")
def program_submit(programId: int = Path(...), user=Depends(_PROG_SUBMIT)):
    return success(prog_svc.submit_program(programId, user), message="已提交")


@router.post("/programs/{programId}/review", summary="方案两级审核（学院→教务→PUBLISHED）")
def program_review(body: AaReviewBody, programId: int = Path(...), user=Depends(_PROG_REVIEW)):
    return success(prog_svc.review_program(programId, user, body.action, body.reason or ""), message="已处理")


class BindGradeBody(BaseModel):
    gradeYear: str = Field(..., min_length=1)
    classId: Optional[str] = None


@router.post("/programs/{programId}/bind", summary="已发布方案绑定年级（锁旧版本）")
def program_bind(body: BindGradeBody, programId: int = Path(...), user=Depends(_PROG_PUBLISH)):
    return success(prog_svc.bind_grade(programId, user, body.gradeYear, body.classId), message="已绑定")


@router.get("/programs/{programId}/bindings", summary="方案发布：已绑定年级记录（含历史 SUPERSEDED）")
def program_bindings(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_program_bindings(programId, user)})


# ── 学分要求（学分结构：分模块学分目标） ──

class CreditRequirementItem(BaseModel):
    module: str = Field(..., min_length=1)
    creditTarget: float = Field(..., ge=0)
    note: Optional[str] = None


class CreditRequirementsBody(BaseModel):
    items: List[CreditRequirementItem] = Field(default_factory=list)


@router.get("/programs/{programId}/credit-requirements", summary="学分要求：分模块学分结构读取")
def program_credit_requirements(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success(prog_svc.get_credit_requirements(programId, user))


@router.put("/programs/{programId}/credit-requirements", summary="学分要求：保存分模块学分结构（编制态）")
def program_credit_requirements_save(body: CreditRequirementsBody, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    items = [i.model_dump() for i in body.items]
    return success(prog_svc.save_credit_requirements(programId, user, items), message="已保存")


# ── 毕业要求（结构化条目 CRUD） ──

class GraduationRequirementCreate(BaseModel):
    category: Optional[str] = Field("ABILITY", description="KNOWLEDGE/ABILITY/QUALITY/CERTIFICATE")
    content: str = Field(..., min_length=1, max_length=1000)
    sortOrder: Optional[int] = None


class GraduationRequirementUpdate(BaseModel):
    category: Optional[str] = None
    content: Optional[str] = Field(None, max_length=1000)
    sortOrder: Optional[int] = None


@router.get("/programs/{programId}/graduation-requirements", summary="毕业要求：条目列表")
def program_grad_requirements(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_graduation_requirements(programId, user)})


@router.post("/programs/{programId}/graduation-requirements", summary="毕业要求：新增条目（编制态）")
def program_grad_requirement_create(body: GraduationRequirementCreate, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.create_graduation_requirement(programId, user, body), message="已添加")


@router.put("/programs/graduation-requirements/{requirementId}", summary="毕业要求：编辑条目（编制态）")
def program_grad_requirement_update(body: GraduationRequirementUpdate, requirementId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.update_graduation_requirement(requirementId, user, body), message="已保存")


@router.delete("/programs/graduation-requirements/{requirementId}", summary="毕业要求：删除条目（编制态）")
def program_grad_requirement_delete(requirementId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.delete_graduation_requirement(requirementId, user), message="已删除")


# ── 方案版本（新建版本 + 版本链） ──

@router.get("/programs/{programId}/versions", summary="方案版本：同一方案谱系全部版本链")
def program_versions(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_program_versions(programId, user)})


@router.post("/programs/{programId}/new-version", summary="方案版本：基于已发布/启用/冻结版本新建 DRAFT 新版本")
def program_new_version(programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.create_new_version(programId, user), message="已新建版本")


# ═══════════ 课程库（P3，两级审核，商业级全字段）═══════════

class CourseCreate(BaseModel):
    courseCode: str = Field(..., min_length=1)
    courseName: str = Field(..., min_length=1)
    courseNameEn: Optional[str] = None
    category: str = Field("MAJOR_CORE", description="PUBLIC_BASIC/DISCIPLINE_BASIC/MAJOR_CORE/MAJOR_ELECTIVE/PRACTICE")
    nature: str = Field("REQUIRED", description="REQUIRED/ELECTIVE/LIMITED_ELECTIVE/PUBLIC_ELECTIVE")
    credit: float = Field(0)
    hoursTotal: Optional[int] = None
    hoursTheory: Optional[int] = None
    hoursPractice: Optional[int] = None
    hoursExperiment: Optional[int] = None
    hoursComputer: Optional[int] = None
    examMode: str = Field("EXAM", description="EXAM/CHECK")
    ownerCollegeId: Optional[str] = None
    isCore: bool = Field(False)
    prerequisiteCodes: Optional[list] = Field(default_factory=list)


@router.post("/courses", summary="新建课程（草稿）")
def course_create(body: CourseCreate, user=Depends(require_staff)):
    return success(course_svc.create_course(body, user), message="已创建")


@router.get("/courses", summary="课程库列表")
def courses(keyword: Optional[str] = None, category: Optional[str] = None, nature: Optional[str] = None,
            status: Optional[str] = None, page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = course_svc.list_courses(user, keyword, category, nature, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/courses/{courseId}", summary="课程详情")
def course_detail(courseId: int = Path(...), user=Depends(require_staff)):
    return success(course_svc.get_course(courseId, user))


@router.put("/courses/{courseId}", summary="编辑课程（已启用改动强制新版本）")
def course_update(body: CourseCreate, courseId: int = Path(...), user=Depends(require_staff)):
    return success(course_svc.update_course(courseId, user, body), message="已保存")


@router.post("/courses/{courseId}/submit", summary="提交课程审核")
def course_submit(courseId: int = Path(...), user=Depends(require_staff)):
    return success(course_svc.submit_course(courseId, user), message="已提交")


@router.post("/courses/{courseId}/review", summary="课程两级审核（学院→教务→ENABLED）")
def course_review(body: AaReviewBody, courseId: int = Path(...), user=Depends(require_staff)):
    return success(course_svc.review_course(courseId, user, body.action, body.reason or ""), message="已处理")


# ═══════════ 教学任务（P3）═══════════

class TaskBatchGenerate(BaseModel):
    termId: str = Field(..., min_length=1)
    collegeId: Optional[str] = None
    batchName: Optional[str] = None


class AssignBody(BaseModel):
    teacherId: Optional[str] = None
    teacherKey: Optional[str] = None
    teacherName: str = Field(..., min_length=1)
    weeklyHours: Optional[int] = None
    expectedStudents: Optional[int] = None
    isMerged: Optional[bool] = None


class TeacherActBody(BaseModel):
    action: str = Field(..., description="CONFIRM/REJECT")
    reason: Optional[str] = Field("", max_length=500)


@router.post("/teaching-task-batches/generate", summary="生成教学任务批次（按已发布方案，幂等）")
def task_generate(body: TaskBatchGenerate, user=Depends(require_staff)):
    return success(task_svc.generate_batch(body, user), message="已生成")


@router.get("/teaching-task-batches", summary="教学任务批次列表")
def task_batches(termId: Optional[str] = None, status: Optional[str] = None,
                 page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = task_svc.list_batches(user, termId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/teaching-task-batches/{batchId}/submit", summary="提交批次审核（要求全部已分配）")
def task_batch_submit(batchId: int = Path(...), user=Depends(require_staff)):
    return success(task_svc.submit_batch(batchId, user), message="已提交")


@router.get("/teaching-task-batches/{batchId}/tasks", summary="批次内教学任务列表")
def task_list(batchId: int = Path(...), status: Optional[str] = None,
              page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = task_svc.list_tasks(batchId, user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/teaching-tasks/{taskId}/assign", summary="分配授课教师")
def task_assign(body: AssignBody, taskId: int = Path(...), user=Depends(require_staff)):
    return success(task_svc.assign_teacher(taskId, user, body), message="已分配")


@router.post("/teaching-tasks/{taskId}/teacher-act", summary="教师确认/退回教学任务")
def task_teacher_act(body: TeacherActBody, taskId: int = Path(...), user=Depends(require_staff)):
    return success(task_svc.teacher_act(taskId, user, body.action, body.reason or ""), message="已处理")


# ── 教学任务确认（教务两级，Tier1 R1 新增）──

@router.post("/teaching-task-batches/{batchId}/college-confirm", summary="学院核对确认（DRAFT→COLLEGE_CONFIRMED）")
def task_batch_college_confirm(batchId: int = Path(...),
                               user=Depends(require_permission("academicAffairs.teachingTask.confirm"))):
    return success(task_svc.college_confirm_batch(batchId, user), message="已确认")


@router.post("/teaching-task-batches/{batchId}/review", summary="教务终审（COLLEGE_CONFIRMED→APPROVED/RETURNED）")
def task_batch_review(body: AaReviewBody, batchId: int = Path(...),
                      user=Depends(require_permission("academicAffairs.teachingTask.confirm"))):
    return success(task_svc.review_batch(batchId, user, body.action, body.reason or ""), message="已处理")


# ── 任课教师分配 / 教师任务确认：跨批次工作队列（Tier1 R1 新增）──

@router.get("/teaching-tasks", summary="跨批次教学任务列表（分配队列/合班候选/我的任务）")
def task_all_list(batchId: Optional[int] = None, courseId: Optional[int] = None,
                  status: Optional[str] = None, mergeable: bool = False, mine: bool = False,
                  page: int = 1, pageSize: int = 50,
                  user=Depends(require_permission("academicAffairs.teachingTask.view"))):
    items, total = task_svc.list_all_tasks(user, batchId, courseId, status, mergeable, mine, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ── 合班 / 拆班（Tier1 R1 新增）──

class MergeTasksBody(BaseModel):
    taskIds: list[str] = Field(..., min_length=2)
    note: Optional[str] = Field("", max_length=500)


@router.post("/teaching-tasks/merge", summary="合班（同批次同课程 2+ 条任务合并为一条教学班任务）")
def task_merge(body: MergeTasksBody, user=Depends(require_permission("academicAffairs.teachingTask.merge"))):
    return success(task_svc.merge_tasks(body, user), message="已合班")


@router.post("/teaching-tasks/{taskId}/split", summary="拆班（还原合班前的独立教学任务）")
def task_split(taskId: int = Path(...), user=Depends(require_permission("academicAffairs.teachingTask.merge"))):
    return success(task_svc.split_task(taskId, user), message="已拆班")


# ── 教学任务统计（Tier1 R1 新增）──

@router.get("/teaching-task-batches/stats", summary="教学任务统计（批次/任务状态分布+分配率+教师确认率）")
def task_stats(termId: Optional[str] = None,
               user=Depends(require_permission("academicAffairs.teachingTask.stats"))):
    return success(task_svc.get_task_stats(user, termId))


# ═══════════ 课表（P4，三重冲突检测 + 单双周 + 三视图）═══════════

class ScheduleBatchCreate(BaseModel):
    termId: str = Field(..., min_length=1)
    batchName: Optional[str] = None
    collegeId: Optional[str] = None


class ScheduleItemBody(BaseModel):
    taskId: Optional[str] = None
    courseName: Optional[str] = None
    classId: Optional[str] = None
    className: Optional[str] = None
    teacherKey: Optional[str] = None
    teacherName: Optional[str] = None
    weekday: int = Field(..., ge=1, le=7, description="星期 1-7")
    slotNo: int = Field(..., ge=1, description="节次")
    startWeek: int = Field(1, ge=1)
    endWeek: int = Field(18, ge=1)
    weekParity: str = Field("ALL", description="ALL/ODD/EVEN 全周/单周/双周")
    classroom: Optional[str] = None


class ScheduleImportBody(BaseModel):
    items: list[dict] = Field(..., description="课表行数组（同一冲突检测器逐行校验）")


class VoidBody(BaseModel):
    reason: str = Field(..., min_length=1)


@router.post("/schedule-batches", summary="新建课表批次")
def schedule_batch_create(body: ScheduleBatchCreate, user=Depends(require_staff)):
    return success(sched_svc.create_batch(body, user), message="已创建")


@router.get("/schedule-batches", summary="课表批次列表")
def schedule_batches(termId: Optional[str] = None, status: Optional[str] = None,
                     page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = sched_svc.list_batches(user, termId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/schedule-batches/{batchId}/items", summary="手工排课（三重冲突检测→409）")
def schedule_add_item(body: ScheduleItemBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.add_item(batchId, user, body), message="已排课")


@router.post("/schedule-batches/{batchId}/import", summary="导入课表（同一冲突检测器，返回冲突清单）")
def schedule_import(body: ScheduleImportBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.import_items(batchId, user, body.items), message="导入完成")


@router.post("/schedule-batches/{batchId}/pre-publish", summary="课表预发布")
def schedule_pre_publish(batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.pre_publish(batchId, user), message="已预发布")


@router.post("/schedule-batches/{batchId}/publish", summary="课表发布（通知师生）")
def schedule_publish(batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.publish(batchId, user), message="已发布")


@router.post("/schedule-batches/{batchId}/void-reissue", summary="作废重发（调停课运维通道，留审计）")
def schedule_void(body: VoidBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.void_and_reissue(batchId, user, body.reason), message="已作废")


@router.get("/schedule-batches/{batchId}/class-view", summary="班级课表视图")
def schedule_class_view(batchId: int = Path(...), classId: str = "", user=Depends(require_staff)):
    return success(sched_svc.class_view(batchId, user, classId))


@router.get("/schedule-batches/{batchId}/teacher-view", summary="教师课表视图")
def schedule_teacher_view(batchId: int = Path(...), teacherKey: str = "", user=Depends(require_staff)):
    return success(sched_svc.teacher_view(batchId, user, teacherKey))


@router.get("/schedule-batches/{batchId}/student-view", summary="学生课表视图（按行政班服务端推导）")
def schedule_student_view(batchId: int = Path(...), studentId: str = "", user=Depends(require_staff)):
    return success(sched_svc.student_view(batchId, user, studentId))


# ═══════════ 成绩录入 + 读侧视图（P5，平时+期末按比例）═══════════

class GradeTaskCreate(BaseModel):
    teachingTaskId: Optional[str] = None
    termId: Optional[str] = None
    termCode: Optional[str] = None
    courseName: str = Field(..., min_length=1)
    classId: Optional[str] = None
    credit: Optional[float] = None
    usualRatio: int = Field(30, ge=0, le=100, description="平时占比%")
    finalRatio: int = Field(70, ge=0, le=100, description="期末占比%")
    passLine: int = Field(60, ge=0, le=100)


class ScoreBody(BaseModel):
    studentId: str = Field(..., min_length=1)
    usualScore: Optional[int] = Field(None, ge=0, le=100)
    finalScore: Optional[int] = Field(None, ge=0, le=100)
    exceptionFlag: Optional[str] = Field(None, description="NORMAL/ABSENT/DEFERRED/EXEMPT")


class GradeReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/RETURN")
    reason: Optional[str] = Field("", max_length=500)


class GradeReturnBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class GradeChangeRequestBody(BaseModel):
    newUsualScore: Optional[int] = Field(None, ge=0, le=100)
    newFinalScore: Optional[int] = Field(None, ge=0, le=100)
    reason: str = Field(..., min_length=5, max_length=500)
    attachmentIds: Optional[list] = Field(default_factory=list)


class GradeChangeReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    reason: Optional[str] = Field("", max_length=500)


@router.post("/grade-tasks", summary="新建成绩录入任务（配平时/期末占比）")
def grade_task_create(body: GradeTaskCreate, user=Depends(require_permission("academicAffairs.grade.input"))):
    return success(grade_svc.create_grade_task(body, user), message="已创建")


@router.get("/grade-tasks", summary="成绩录入任务列表（按状态筛选，供审核/发布工作台队列）")
def grade_tasks(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                user=Depends(require_permission("academicAffairs.grade.view"))):
    items, total = grade_svc.list_tasks(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/grade-tasks/{taskId}/roster", summary="教学班学生名单（供录入圈定）")
def grade_roster(taskId: int = Path(...), user=Depends(require_permission("academicAffairs.grade.input"))):
    return success(grade_svc.roster(taskId, user))


@router.post("/grade-tasks/{taskId}/scores", summary="录入平时/期末分（实时合成总评）")
def grade_enter_score(body: ScoreBody, taskId: int = Path(...),
                      user=Depends(require_permission("academicAffairs.grade.input"))):
    return success(grade_svc.enter_score(taskId, user, body), message="已录入")


@router.post("/grade-tasks/{taskId}/submit", summary="提交成绩进入学院审核")
def grade_submit(taskId: int = Path(...), user=Depends(require_permission("academicAffairs.grade.submit"))):
    return success(grade_svc.submit_task(taskId, user), message="已提交")


@router.post("/grade-tasks/{taskId}/college-review", summary="学院审核成绩（通过/退回）")
def grade_college_review(body: GradeReviewBody, taskId: int = Path(...),
                         user=Depends(require_permission("academicAffairs.grade.collegeReview"))):
    return success(grade_svc.college_review(taskId, user, body.action, body.reason or ""), message="已处理")


@router.post("/grade-tasks/{taskId}/publish", summary="教务处终审发布（原子回写+台账刷新+预警）")
def grade_publish(taskId: int = Path(...), user=Depends(require_permission("academicAffairs.grade.publish"))):
    return success(grade_svc.publish_grades(taskId, user), message="已发布")


@router.post("/grade-tasks/{taskId}/return", summary="教务处退回（教务终审阶段）")
def grade_return(body: GradeReturnBody, taskId: int = Path(...),
                 user=Depends(require_permission("academicAffairs.grade.return"))):
    return success(grade_svc.return_task(taskId, user, body.reason), message="已退回")


@router.post("/grade-tasks/{taskId}/archive", summary="学期归档（仅已发布任务）")
def grade_archive(taskId: int = Path(...), user=Depends(require_permission("academicAffairs.grade.archive"))):
    return success(grade_svc.archive_task(taskId, user), message="已归档")


@router.post("/grade-tasks/{taskId}/records/{recordId}/change-request", summary="教师发起成绩更正")
def grade_change_request(body: GradeChangeRequestBody, taskId: int = Path(...), recordId: int = Path(...),
                         user=Depends(require_permission("academicAffairs.gradeChange.apply"))):
    return success(grade_svc.change_request(taskId, recordId, user, body), message="更正申请已提交")


@router.post("/grade-change/{recordId}/college-review", summary="成绩更正学院初审")
def grade_change_college_review(body: GradeChangeReviewBody, recordId: int = Path(...),
                                user=Depends(require_permission("academicAffairs.gradeChange.review"))):
    return success(grade_svc.change_college_review(recordId, user, body.action, body.reason or ""), message="已处理")


@router.post("/grade-change/{recordId}/academic-review", summary="成绩更正教务处终审")
def grade_change_academic_review(body: GradeChangeReviewBody, recordId: int = Path(...),
                                 user=Depends(require_permission("academicAffairs.gradeChange.review"))):
    return success(grade_svc.change_academic_review(recordId, user, body.action, body.reason or ""), message="已处理")


@router.get("/students/{studentId}/transcript", summary="学生成绩单（读侧）")
def grade_transcript(studentId: int = Path(...), user=Depends(require_permission("academicAffairs.grade.view"))):
    return success(grade_svc.transcript(studentId, user))


@router.get("/grade-views/fail-list", summary="挂科清单（读侧下钻）")
def grade_fail_list(term: Optional[str] = None, page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = grade_svc.fail_list(user, term, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/grade-views/analysis", summary="成绩分析（分数段分布+及格率）")
def grade_analysis(term: Optional[str] = None, user=Depends(require_staff)):
    return success(grade_svc.grade_analysis(user, term))


# ═══════════ 学业预警（P5 规则引擎 + 二级模块 Tier1：看板/多维分类/规则/跟进/统计）═══════════
# 权限：view=看板/列表/统计只读；handle=指派/干预/升级/关闭/作废/提醒；rule.manage=规则配置+扫描触发（仅教务处，矩阵 §15）。
_WARN_VIEW = "academicAffairs.warning.view"
_WARN_HANDLE = "academicAffairs.warning.handle"
_WARN_RULE = "academicAffairs.warning.rule.manage"


class WarningAssignBody(BaseModel):
    ownerId: Optional[str] = None
    ownerName: str = Field(..., min_length=1)


class WarningInterventionBody(BaseModel):
    way: str = Field("TALK", description="TALK/PHONE/FAMILY/PLAN")
    content: str = Field(..., min_length=1)
    result: Optional[str] = ""
    nextPlan: Optional[str] = ""


class WarningReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class WarningResultBody(BaseModel):
    result: str = Field(..., min_length=1)


class WarningRuleSaveBody(BaseModel):
    value: float = Field(..., description="规则阈值（int 规则取整数部分）")


@router.post("/warnings/scan", summary="学业预警扫描（挂科规则，幂等）")
def warning_scan(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_warnings(user))


@router.post("/warnings/scan/credit", summary="学分预警扫描（学分完成率，幂等）")
def warning_scan_credit(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_credit_warnings(user))


@router.post("/warnings/scan/gpa", summary="绩点预警扫描（幂等）")
def warning_scan_gpa(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_gpa_warnings(user))


@router.post("/warnings/scan/retake", summary="补考重修预警扫描（幂等）")
def warning_scan_retake(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_retake_warnings(user))


@router.post("/warnings/scan/graduation", summary="毕业风险预警扫描（联动毕业预审 SYSTEM_ABNORMAL，幂等）")
def warning_scan_graduation(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_graduation_warnings(user))


@router.post("/warnings/scan/all", summary="预警看板一键扫描（5 类规则，幂等）")
def warning_scan_all(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_all(user))


@router.get("/warnings/rules", summary="预警规则阈值列表")
def warning_rules(user=Depends(require_permission(_WARN_RULE))):
    return success({"items": warn_svc.get_rules(user)})


@router.put("/warnings/rules/{key}", summary="保存预警规则阈值")
def warning_rule_save(body: WarningRuleSaveBody, key: str = Path(...),
                      user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.save_rule(user, key, body.value), message="已保存")


@router.get("/warnings/summary", summary="预警看板/统计聚合（按来源/等级/状态分组）")
def warning_summary(user=Depends(require_permission(_WARN_VIEW))):
    return success(warn_svc.warning_summary(user))


@router.get("/warnings", summary="学业预警列表（支持来源多维筛选：挂科/学分/绩点/补考重修/毕业风险）")
def warnings(level: Optional[str] = None, status: Optional[str] = None, sourceCode: Optional[str] = None,
             page: int = 1, pageSize: int = 20, user=Depends(require_permission(_WARN_VIEW))):
    items, total = warn_svc.list_warnings(user, level, status, sourceCode, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/warnings/{warningId}", summary="学业预警详情（含学生信息+跟进记录）")
def warning_detail(warningId: int = Path(...), user=Depends(require_permission(_WARN_VIEW))):
    return success(warn_svc.get_warning_detail(user, warningId))


@router.post("/warnings/{warningId}/assign", summary="指派预警跟进人")
def warning_assign(body: WarningAssignBody, warningId: int = Path(...),
                   user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.assign_warning(user, warningId, body.ownerId, body.ownerName), message="已指派")


@router.post("/warnings/{warningId}/interventions", summary="新增预警跟进记录（内容≥5字）")
def warning_intervention(body: WarningInterventionBody, warningId: int = Path(...),
                         user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.add_intervention(user, warningId, body.way, body.content, body.result or "",
                                             body.nextPlan or ""), message="已记录")


@router.post("/warnings/{warningId}/escalate", summary="升级预警（说明≥5字）")
def warning_escalate(body: WarningReasonBody, warningId: int = Path(...),
                     user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.escalate_warning(user, warningId, body.reason), message="已升级")


@router.post("/warnings/{warningId}/close", summary="关闭预警（说明≥5字）")
def warning_close(body: WarningResultBody, warningId: int = Path(...),
                  user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.close_warning(user, warningId, body.result), message="已关闭")


@router.post("/warnings/{warningId}/void", summary="作废预警（误报原因≥5字）")
def warning_void(body: WarningReasonBody, warningId: int = Path(...),
                 user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.void_warning(user, warningId, body.reason), message="已作废")


@router.post("/warnings/{warningId}/remind", summary="提醒预警责任人")
def warning_remind(warningId: int = Path(...), user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.remind_warning(user, warningId), message="已提醒")


# ═══════════ 毕业资格审核（Tier1：十项供数三态判定 + 学院初审→教务终审→归档）═══════════
# permissionKey 收敛为 academicAffairs.graduation.*（manage=批次管理/预审/归档；
# collegeReview=学院初审；final=教务终审；view=只读），均命中既有 academicAffairs.* 角色通配，
# 无需另行注册。超高危动作（建批次/预审/终审/归档）另在 service 内联校验角色白名单（同成绩终审惯例）。
_GRAD_MANAGE = "academicAffairs.graduation.manage"
_GRAD_VIEW = "academicAffairs.graduation.view"
_GRAD_COLLEGE_REVIEW = "academicAffairs.graduation.collegeReview"
_GRAD_FINAL = "academicAffairs.graduation.final"


class GradAuditBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    gradeYear: Optional[str] = None
    majorId: Optional[str] = None


class GenerateStudentsBody(BaseModel):
    studentIds: Optional[list[str]] = None


class GradReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    note: Optional[str] = Field("", max_length=500)


class GradFinalBody(BaseModel):
    conclusion: str = Field(..., description="GRADUATED/COMPLETED/DELAYED")
    confirm: bool = Field(False, description="二次确认(涉学籍终态)")


@router.get("/graduation-audit-batches", summary="审核批次列表（附应审/通过/异常/已终审/已归档统计）")
def grad_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                 user=Depends(require_any_permission(_GRAD_VIEW, _GRAD_MANAGE))):
    items, total = grad_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/graduation-audit-batches", summary="新建毕业资格审核批次")
def grad_batch_create(body: GradAuditBatchCreate, user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.create_batch(body, user), message="已创建")


@router.post("/graduation-audit-batches/{batchId}/generate", summary="圈定应届生生成预审行（幂等）")
def grad_generate(body: GenerateStudentsBody = GenerateStudentsBody(), batchId: int = Path(...),
                  user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.generate(batchId, user, body.studentIds), message="已生成")


@router.post("/graduation-audit-batches/{batchId}/precheck", summary="十项供数三态预审（幂等，覆盖）")
def grad_precheck(batchId: int = Path(...), user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.precheck(batchId, user), message="预审完成")


@router.post("/graduation-audit-batches/{batchId}/archive", summary="审核归档（收敛已终审毕业/结业结果）")
def grad_archive(batchId: int = Path(...), user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.archive_batch(batchId, user), message="已归档")


@router.get("/graduation-audit-batches/{batchId}/results", summary="预审结果列表（支持按单项透视过滤）")
def grad_results(batchId: int = Path(...), status: Optional[str] = None, overall: Optional[str] = None,
                 item: Optional[str] = None, itemResult: Optional[str] = None,
                 page: int = 1, pageSize: int = 50, user=Depends(require_permission(_GRAD_VIEW))):
    items, total = grad_svc.list_results(batchId, user, status, overall, item, itemResult, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/graduation-audit-batches/{batchId}/rosters", summary="三名单（毕业/结业/延毕）")
def grad_rosters(batchId: int = Path(...), user=Depends(require_permission(_GRAD_VIEW))):
    return success(grad_svc.rosters(batchId, user))


@router.get("/graduation-results/{resultId}", summary="预审结果详情（十项证据）")
def grad_result_detail(resultId: int = Path(...), user=Depends(require_permission(_GRAD_VIEW))):
    return success(grad_svc.get_result(resultId, user))


@router.post("/graduation-results/{resultId}/college-review", summary="学院初审")
def grad_college_review(body: GradReviewBody, resultId: int = Path(...),
                        user=Depends(require_permission(_GRAD_COLLEGE_REVIEW))):
    return success(grad_svc.college_review(resultId, user, body.action, body.note or ""), message="已处理")


@router.post("/graduation-results/{resultId}/final", summary="毕业资格终审（结论→经单一入口写学籍，强制二次确认）")
def grad_final(body: GradFinalBody, resultId: int = Path(...), user=Depends(require_permission(_GRAD_FINAL))):
    return success(grad_svc.academic_final(resultId, user, body.conclusion, body.confirm), message="已终审")


# ══════════════ 教务统计（只读聚合，/academic-affairs/stats/*） ══════════════
# 全部端点挂 require_permission("academicAffairs.stats.*")（通配 academicAffairs.* 覆盖教务处/学院/教师；
# LEADER 命中 *.view）；数据范围复用 build_affairs_context（详见 stats_service）。学生令牌 STAFF/STUDENT 无授权 → 403。
_STATS_VIEW = "academicAffairs.stats.view"
_STATS_EXPORT = "academicAffairs.stats.export"


@router.get("/stats/overview", summary="教务统计总览（11 项指标 + 4 项占位）")
def stats_overview(termId: Optional[int] = None, collegeId: Optional[int] = None,
                   majorId: Optional[int] = None, user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.overview(user, termId, collegeId, majorId))


@router.get("/stats/filters", summary="统计筛选器候选（学期/学院/专业，受数据范围收敛）")
def stats_filters(user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.filters(user))


@router.get("/stats/registration", summary="注册统计下钻：未注册学生名单（脱敏+审计）")
def stats_registration(termId: Optional[int] = None, collegeId: Optional[int] = None,
                       majorId: Optional[int] = None, page: int = 1, pageSize: int = 20,
                       user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.registration_unregistered(user, termId, collegeId, majorId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/status-change", summary="学籍统计下钻：EFFECTIVE 异动明细")
def stats_status_change(changeType: Optional[str] = None, termId: Optional[int] = None,
                        collegeId: Optional[int] = None, page: int = 1, pageSize: int = 20,
                        user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.status_change_detail(user, changeType, termId, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/warning", summary="学业预警统计下钻：非 CLOSED 预警明细（脱敏+审计）")
def stats_warning(level: Optional[str] = None, source: Optional[str] = None,
                  collegeId: Optional[int] = None, page: int = 1, pageSize: int = 20,
                  user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.warning_detail(user, level, source, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


class StatsExportBody(BaseModel):
    domain: Optional[str] = "overview"
    termId: Optional[int] = None
    collegeId: Optional[int] = None
    majorId: Optional[int] = None
    purpose: str = Field(..., min_length=5, description="导出用途（≥5 字，必填，写审计）")


@router.post("/stats/export", summary="教务统计导出 xlsx（15 号卡「导出报表」，domain 选择，水印+审计，同步下载）")
def stats_export(body: StatsExportBody, user=Depends(require_permission(_STATS_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content = stats_svc.export_stats_xlsx(user, body.domain, body.termId, body.collegeId,
                                          body.majorId, body.purpose)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=academic_affairs_stats.xlsx"})


# ── Tier1 10 项三级模块（02/03/04/05/06/10/11/12/13/15 号卡）：既有 status-change/registration/warning
#    三个路径已被总览下钻占用（返回明细列表），聚合端点改 `/summary` 后缀，其余为全新路径。
@router.get("/stats/status-change/summary", summary="学籍统计聚合（按 change_type 分组，02 号卡）")
def stats_status_change_summary(termId: Optional[int] = None, collegeId: Optional[int] = None,
                                user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.status_change_stats(user, termId, collegeId))


@router.get("/stats/registration/summary", summary="注册统计聚合（完成率，03 号卡）")
def stats_registration_summary(termId: Optional[int] = None, collegeId: Optional[int] = None,
                               majorId: Optional[int] = None,
                               user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.registration_stats(user, termId, collegeId, majorId))


@router.get("/stats/course", summary="课程统计聚合（按类别/学院双维，04 号卡）")
def stats_course(category: Optional[str] = None, collegeId: Optional[int] = None,
                 user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.course_stats(user, category, collegeId))


@router.get("/stats/course/detail", summary="课程统计下钻：ENABLED 课程明细（04 号卡）")
def stats_course_detail(category: Optional[str] = None, collegeId: Optional[int] = None,
                        page: int = 1, pageSize: int = 20,
                        user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.course_detail(user, category, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/teaching-task", summary="教学任务统计聚合（确认完成率，05 号卡）")
def stats_teaching_task(collegeId: Optional[int] = None, termId: Optional[int] = None,
                        user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.teaching_task_stats(user, collegeId, termId))


@router.get("/stats/teaching-task/pending", summary="教学任务统计下钻：未确认任务清单（05 号卡）")
def stats_teaching_task_pending(collegeId: Optional[int] = None, termId: Optional[int] = None,
                                page: int = 1, pageSize: int = 20,
                                user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.teaching_task_pending(user, collegeId, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/schedule", summary="课表统计聚合（发布覆盖率+未解决冲突数，06 号卡）")
def stats_schedule(collegeId: Optional[int] = None, termId: Optional[int] = None,
                   user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.schedule_stats(user, collegeId, termId))


@router.get("/stats/schedule/conflicts", summary="课表统计下钻：冲突明细（06 号卡）")
def stats_schedule_conflicts(collegeId: Optional[int] = None, termId: Optional[int] = None,
                             page: int = 1, pageSize: int = 20,
                             user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.schedule_conflicts(user, collegeId, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/grade", summary="成绩统计聚合（挂科率+录入发布率+补考重修人数，10 号卡）")
def stats_grade(termId: Optional[int] = None, collegeId: Optional[int] = None,
                user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.grade_stats(user, termId, collegeId))


@router.get("/stats/grade/detail", summary="成绩统计下钻：挂科学生明细（脱敏+审计，10 号卡）")
def stats_grade_detail(termId: Optional[int] = None, collegeId: Optional[int] = None,
                       courseName: Optional[str] = None, page: int = 1, pageSize: int = 20,
                       user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.grade_detail(user, termId, collegeId, courseName, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/warning/summary", summary="学业预警统计聚合（按等级/来源双维，11 号卡）")
def stats_warning_summary(termId: Optional[int] = None, collegeId: Optional[int] = None,
                          user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.warning_stats(user, termId, collegeId))


@router.get("/stats/graduation", summary="毕业资格统计聚合（通过率+异常项分布，12 号卡）")
def stats_graduation(batchId: Optional[int] = None, collegeId: Optional[int] = None,
                     user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.graduation_stats(user, batchId, collegeId))


@router.get("/stats/graduation/abnormal", summary="毕业资格统计下钻：异常项学生名单（脱敏+审计，12 号卡）")
def stats_graduation_abnormal(batchId: Optional[int] = None, collegeId: Optional[int] = None,
                              itemType: Optional[str] = None, page: int = 1, pageSize: int = 20,
                              user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.graduation_abnormal(user, batchId, collegeId, itemType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/workload", summary="教师工作量统计聚合（ai_proposal，基础参考非正式核算，13 号卡）")
def stats_workload(termId: Optional[int] = None, collegeId: Optional[int] = None,
                   user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.workload_stats(user, termId, collegeId))


@router.get("/stats/workload/detail", summary="教师工作量统计下钻：单教师授课明细（13 号卡）")
def stats_workload_detail(teacherKey: str, collegeId: Optional[int] = None,
                          page: int = 1, pageSize: int = 20,
                          user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.workload_detail(user, teacherKey, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))




# ═══════════════════════════════════════════════════════════════════════════
# 13B-R3 学院专业班级（组织架构）—— /academic-affairs/orgs/*
# 组织三表加列复用（不建新表）；读=academicAffairs.org.view，写=academicAffairs.org.manage。
# 数据范围经 build_affairs_context：TENANT_ALL 全租户 / COLLEGE 限授权学院 / 其它 fail-closed。
# ═══════════════════════════════════════════════════════════════════════════

_ORG_VIEW = require_permission("academicAffairs.org.view")
_ORG_MANAGE = require_permission("academicAffairs.org.manage")


class CollegeBody(BaseModel):
    collegeName: Optional[str] = None
    code: Optional[str] = None
    shortName: Optional[str] = None
    sortOrder: Optional[int] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class SecretaryBindBody(BaseModel):
    secretaryId: Optional[str] = None


class MajorBody(BaseModel):
    collegeId: Optional[str] = None
    majorName: Optional[str] = None
    code: Optional[str] = None
    educationYears: Optional[int] = Field(None, ge=1, le=10)
    trainingLevel: Optional[str] = None
    enrollStatus: Optional[str] = None
    direction: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class ClassBody(BaseModel):
    majorId: Optional[str] = None
    className: Optional[str] = None
    classCode: Optional[str] = None
    grade: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)
    graduateYear: Optional[str] = None
    classStatus: Optional[str] = None
    counselorId: Optional[str] = None
    headTeacherId: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class ClassAdjustBody(BaseModel):
    studentId: str = Field(..., min_length=1)
    targetClassId: str = Field(..., min_length=1)


# ── 学院 ──
@router.get("/orgs/colleges", summary="学院列表（范围内）")
def org_colleges(keyword: Optional[str] = None, status: Optional[str] = None,
                 page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_colleges(user, keyword, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/orgs/colleges", summary="新建学院")
def org_college_create(body: CollegeBody, user=Depends(_ORG_MANAGE)):
    return success(org_svc.create_college(user, body), message="已创建")


@router.put("/orgs/colleges/{collegeId}", summary="编辑学院")
def org_college_update(body: CollegeBody, collegeId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.update_college(user, collegeId, body), message="已保存")


@router.post("/orgs/colleges/{collegeId}/secretary", summary="教学秘书绑定/解绑")
def org_college_secretary(body: SecretaryBindBody, collegeId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.bind_secretary(user, collegeId, body), message="已保存")


@router.delete("/orgs/colleges/{collegeId}", summary="删除学院（软删，须无在册专业）")
def org_college_delete(collegeId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.delete_college(user, collegeId), message="已删除")


# ── 专业 ──
@router.get("/orgs/majors", summary="专业列表（范围内）")
def org_majors(collegeId: Optional[str] = None, enrollStatus: Optional[str] = None,
               keyword: Optional[str] = None, page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_majors(user, collegeId, enrollStatus, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/orgs/majors", summary="新建专业")
def org_major_create(body: MajorBody, user=Depends(_ORG_MANAGE)):
    return success(org_svc.create_major(user, body), message="已创建")


@router.put("/orgs/majors/{majorId}", summary="编辑专业（含专业方向/招生状态）")
def org_major_update(body: MajorBody, majorId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.update_major(user, majorId, body), message="已保存")


@router.delete("/orgs/majors/{majorId}", summary="删除专业（软删，须无在册班级）")
def org_major_delete(majorId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.delete_major(user, majorId), message="已删除")


# ── 行政班 ──
@router.get("/orgs/classes", summary="行政班列表（范围内）")
def org_classes(majorId: Optional[str] = None, grade: Optional[str] = None,
                classStatus: Optional[str] = None, keyword: Optional[str] = None,
                page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_classes(user, majorId, grade, classStatus, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/orgs/classes", summary="新建行政班")
def org_class_create(body: ClassBody, user=Depends(_ORG_MANAGE)):
    return success(org_svc.create_class(user, body), message="已创建")


@router.put("/orgs/classes/{classId}", summary="编辑行政班")
def org_class_update(body: ClassBody, classId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.update_class(user, classId, body), message="已保存")


@router.delete("/orgs/classes/{classId}", summary="删除行政班（软删，须无在册学生）")
def org_class_delete(classId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.delete_class(user, classId), message="已删除")


# ── 年级 / 教学班 / 班级学生 / 班级调整 ──
@router.get("/orgs/grades", summary="年级聚合（班级数/学生数，非独立表）")
def org_grades(collegeId: Optional[str] = None, majorId: Optional[str] = None, user=Depends(_ORG_VIEW)):
    return success(org_svc.list_grades(user, collegeId, majorId))


@router.get("/orgs/teaching-classes", summary="教学班只读汇总（派生自教学任务）")
def org_teaching_classes(termCode: Optional[str] = None, batchId: Optional[str] = None,
                         page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_teaching_classes(user, termCode, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/orgs/classes/{classId}/students", summary="班级学生列表")
def org_class_students(classId: int = Path(...), page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_class_students(user, classId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/orgs/class-adjustments", summary="班级调整（移动学生，单写入口+审计）")
def org_class_adjust(body: ClassAdjustBody, user=Depends(_ORG_MANAGE)):
    return success(org_svc.adjust_student_class(user, body), message="已调整")


# ── 组织树 / 统计 / 变更审计 ──
@router.get("/orgs/tree", summary="组织结构（学院→专业→班级）")
def org_tree(user=Depends(_ORG_VIEW)):
    return success(org_svc.org_tree(user))


@router.get("/orgs/stats", summary="组织统计")
def org_stats(user=Depends(_ORG_VIEW)):
    return success(org_svc.org_stats(user))


@router.get("/orgs/audit", summary="组织变更审计（AA_ORG_*）")
def org_audit(bizType: Optional[str] = None, page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_org_audit(user, bizType, page, pageSize)
    return success(paginate(items, total, page, pageSize))



# ═══════════ 教学资源 · 教室字典（13B-R4；细粒度权限 academicAffairs.classroom.*）═══════════


class ClassroomCreate(BaseModel):
    buildingCode: str = Field(..., min_length=1, description="楼栋编码")
    buildingName: str = Field(..., min_length=1, description="楼栋名称")
    roomCode: str = Field(..., min_length=1, description="教室编号")
    roomName: Optional[str] = None
    capacity: Optional[int] = Field(0, ge=0, description="容量(座位数)")
    roomType: Optional[str] = Field("LECTURE", description="LECTURE/MULTIMEDIA/COMPUTER/LAB/OTHER")
    campusCode: Optional[str] = None
    remark: Optional[str] = None


class ClassroomUpdate(BaseModel):
    buildingCode: Optional[str] = None
    buildingName: Optional[str] = None
    roomCode: Optional[str] = None
    roomName: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)
    roomType: Optional[str] = None
    campusCode: Optional[str] = None
    remark: Optional[str] = None


class ClassroomStatusBody(BaseModel):
    status: str = Field(..., description="AVAILABLE/DISABLED/MAINTENANCE")
    reason: Optional[str] = None


@router.get("/classrooms", summary="教室字典列表（按楼栋/类型/状态/关键词过滤）")
def classroom_list(keyword: Optional[str] = None, buildingCode: Optional[str] = None,
                   roomType: Optional[str] = None, status: Optional[str] = None,
                   page: int = 1, pageSize: int = 20,
                   user=Depends(require_permission("academicAffairs.classroom.view"))):
    items, total = resource_svc.list_classrooms(user, keyword, buildingCode, roomType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/classrooms/options", summary="可用教室选项（排课选择器供数，含 capacity 供非阻断 warning）")
def classroom_options(keyword: Optional[str] = None,
                      user=Depends(require_permission("academicAffairs.classroom.view"))):
    return success({"items": resource_svc.list_options(user, keyword)})


@router.get("/classrooms/{classroomId}", summary="教室详情")
def classroom_detail(classroomId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.classroom.view"))):
    return success(resource_svc.get_classroom(classroomId, user))


@router.post("/classrooms", summary="新建教室（同楼栋+编号唯一，重复409）")
def classroom_create(body: ClassroomCreate,
                     user=Depends(require_permission("academicAffairs.classroom.create"))):
    return success(resource_svc.create_classroom(body, user), message="已创建")


@router.put("/classrooms/{classroomId}", summary="编辑教室")
def classroom_update(body: ClassroomUpdate, classroomId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.classroom.update"))):
    return success(resource_svc.update_classroom(classroomId, body, user), message="已保存")


@router.post("/classrooms/{classroomId}/status", summary="切换可用状态（AVAILABLE/DISABLED/MAINTENANCE，幂等）")
def classroom_status(body: ClassroomStatusBody, classroomId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.classroom.update"))):
    return success(resource_svc.set_status(classroomId, body.status, user, body.reason or ""), message="已更新")


@router.delete("/classrooms/{classroomId}", summary="删除教室（逻辑删除）")
def classroom_delete(classroomId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.classroom.delete"))):
    return success(resource_svc.delete_classroom(classroomId, user), message="已删除")


# ── 教室预约（占用登记+冲突检测+审核） ──
class ClassroomBookBody(BaseModel):
    classroomId: str = Field(..., min_length=1)
    bookingDate: str = Field(..., min_length=1, description="YYYY-MM-DD")
    slotNo: int = Field(..., ge=1)
    purpose: Optional[str] = Field(None, max_length=300)


class BookingReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    reason: Optional[str] = Field("", max_length=300)


@router.post("/classrooms/bookings", summary="申请教室预约（同教室同时段占用409）")
def classroom_book(body: ClassroomBookBody, user=Depends(require_staff)):
    return success(resource_svc.book_classroom(user, body), message="已提交预约")


@router.get("/classrooms/bookings", summary="教室预约列表")
def classroom_bookings(classroomId: Optional[str] = None, date: Optional[str] = None,
                       status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                       user=Depends(require_permission("academicAffairs.classroom.view"))):
    items, total = resource_svc.list_bookings(user, classroomId, date, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/classrooms/bookings/{bookingId}/review", summary="审核教室预约")
def classroom_booking_review(body: BookingReviewBody, bookingId: int = Path(...),
                             user=Depends(require_permission("academicAffairs.classroom.update"))):
    return success(resource_svc.review_booking(user, bookingId, body.action, body.reason), message="已处理")

# ═══════════ 调停课（R2/SM-08，调课/停课/补课；教师发起→学院审→教务处审→改写课表）═══════════

_SC_REVIEW = require_any_permission("academicAffairs.scheduleChange.collegeReview",
                                    "academicAffairs.scheduleChange.academicReview")


class ScheduleChangeSubmit(BaseModel):
    originItemId: str = Field(..., min_length=1, description="原课表项 id（须为已发布课表本人课位）")
    changeType: str = Field(..., description="ADJUST 调课 / STOP 停课 / MAKEUP 补课")
    reason: str = Field(..., min_length=5, max_length=500, description="调停课原因（≥5 字）")
    targetWeekday: Optional[int] = Field(None, ge=1, le=7, description="目标星期（调课/补课必填）")
    targetSlotNo: Optional[int] = Field(None, ge=1, description="目标节次")
    targetStartWeek: Optional[int] = Field(None, ge=1)
    targetEndWeek: Optional[int] = Field(None, ge=1)
    targetWeekParity: Optional[str] = Field(None, description="ALL/ODD/EVEN")
    targetClassroom: Optional[str] = None
    makeupPlan: Optional[str] = Field(None, max_length=500, description="补课/停课后续安排")


class ScheduleChangeReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    comment: Optional[str] = Field("", max_length=500, description="驳回原因（REJECT 时≥5 字）")


class ScheduleChangeCancelBody(BaseModel):
    reason: Optional[str] = Field("", max_length=500)


@router.post("/schedule-change", summary="发起调停课（提交即目标冲突预检；冲突单据不落库）")
def schedule_change_submit(body: ScheduleChangeSubmit,
                           user=Depends(require_permission("academicAffairs.scheduleChange.apply"))):
    return success(sched_change_svc.submit(body, user), message="调停课已提交")


@router.get("/schedule-change", summary="调停课台账（范围过滤）")
def schedule_change_list(changeType: Optional[str] = None, status: Optional[str] = None,
                         teacherKey: Optional[str] = None, termId: Optional[str] = None,
                         page: int = 1, pageSize: int = 20,
                         user=Depends(require_permission("academicAffairs.scheduleChange.view"))):
    items, total = sched_change_svc.list_changes(user, changeType, status, teacherKey, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/schedule-change/stats", summary="调停课统计（按类型/状态聚合）")
def schedule_change_stats(termId: Optional[str] = None,
                          user=Depends(require_permission("academicAffairs.scheduleChange.view"))):
    return success(sched_change_svc.stats(user, termId))


@router.get("/schedule-change/{changeId}", summary="调停课详情（含通知单打印数据）")
def schedule_change_detail(changeId: int = Path(...),
                           user=Depends(require_permission("academicAffairs.scheduleChange.view"))):
    return success(sched_change_svc.get_change(changeId, user))


@router.post("/schedule-change/{changeId}/approve", summary="审批通过（学院/教务处；终审通过即改写课表）")
def schedule_change_approve(body: ScheduleChangeReviewBody = ScheduleChangeReviewBody(action="APPROVE"),
                            changeId: int = Path(...), user=Depends(_SC_REVIEW)):
    return success(sched_change_svc.review(changeId, user, "APPROVE", body.comment or ""), message="已通过")


@router.post("/schedule-change/{changeId}/reject", summary="驳回（原因≥5 字）")
def schedule_change_reject(body: ScheduleChangeReviewBody, changeId: int = Path(...),
                           user=Depends(_SC_REVIEW)):
    return success(sched_change_svc.review(changeId, user, "REJECT", body.comment or ""), message="已驳回")


@router.post("/schedule-change/{changeId}/cancel", summary="撤销（仅 SUBMITTED/COLLEGE_REVIEW，APPROVED 后 409）")
def schedule_change_cancel(body: ScheduleChangeCancelBody = ScheduleChangeCancelBody(),
                           changeId: int = Path(...),
                           user=Depends(require_permission("academicAffairs.scheduleChange.apply"))):
    return success(sched_change_svc.cancel(changeId, user, body.reason or ""), message="已撤销")




# ══════════════ 选课管理（13B-SM-09，/academic-affairs/selection/*） ══════════════
# 权限：academicAffairs.selection.{view|manage|rule.manage|enroll|drop|adjust|lock|rosterView}
# 通配 academicAffairs.* 覆盖教务处/学院/教师；学生令牌经 enroll/drop 细粒度点校验。
_SEL_VIEW = "academicAffairs.selection.view"
_SEL_MANAGE = "academicAffairs.selection.manage"
_SEL_RULE = "academicAffairs.selection.rule.manage"
_SEL_ENROLL = "academicAffairs.selection.enroll"
_SEL_DROP = "academicAffairs.selection.drop"
_SEL_ADJUST = "academicAffairs.selection.adjust"
_SEL_LOCK = "academicAffairs.selection.lock"
_SEL_ROSTER = "academicAffairs.selection.rosterView"


class SelectionBatchBody(BaseModel):
    batchName: str = Field(..., min_length=1)
    termId: Optional[str] = None
    selectStartAt: Optional[str] = None
    selectEndAt: Optional[str] = None
    applyScope: Optional[dict] = None
    rule: Optional[dict] = None
    remark: Optional[str] = None


class SelectionRuleBody(BaseModel):
    rule: dict = Field(default_factory=dict)


class SelectionCourseBody(BaseModel):
    courseId: str = Field(..., min_length=1)
    teachingTaskId: Optional[str] = None
    capacity: int = Field(0, ge=0)
    minCapacity: int = Field(0, ge=0)


class SelectionCourseUpdate(BaseModel):
    capacity: Optional[int] = Field(None, ge=0)
    minCapacity: Optional[int] = Field(None, ge=0)


class EnrollBody(BaseModel):
    selectionCourseId: str = Field(..., min_length=1)


class AdjustBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


# ── 批次（教务处管理 / 教务处·学院只读） ──
@router.post("/selection/batches", summary="建选课批次")
def sel_batch_create(body: SelectionBatchBody, user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.create_batch(user, body), message="已创建")


@router.get("/selection/batches", summary="选课批次列表")
def sel_batches(status: Optional[str] = None, termId: Optional[str] = None,
                page: int = 1, pageSize: int = 20, user=Depends(require_permission(_SEL_VIEW))):
    items, total = selection_svc.list_batches(user, status, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/selection/batches/{batchId}", summary="批次详情")
def sel_batch_detail(batchId: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.get_batch(user, batchId))


@router.post("/selection/batches/{batchId}/publish", summary="发布批次（须已配课程）")
def sel_batch_publish(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.publish_batch(user, batchId), message="已发布")


@router.post("/selection/batches/{batchId}/open", summary="开选（PUBLISHED→OPEN）")
def sel_batch_open(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.open_batch(user, batchId), message="已开选")


@router.post("/selection/batches/{batchId}/close", summary="截止（OPEN→CLOSED）")
def sel_batch_close(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.close_batch(user, batchId), message="已截止")


@router.post("/selection/batches/{batchId}/lock", summary="锁定名单（CLOSED→LOCKED）")
def sel_batch_lock(batchId: int = Path(...), user=Depends(require_permission(_SEL_LOCK))):
    return success(selection_svc.lock_batch(user, batchId), message="已锁定")


@router.post("/selection/batches/{batchId}/archive", summary="归档（LOCKED→ARCHIVED）")
def sel_batch_archive(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.archive_batch(user, batchId), message="已归档")


@router.put("/selection/batches/{batchId}/rule", summary="保存选课规则")
def sel_rule_save(body: SelectionRuleBody, batchId: int = Path(...),
                  user=Depends(require_permission(_SEL_RULE))):
    return success(selection_svc.save_rule(user, batchId, body.rule), message="已保存")


# ── 课程供给 ──
@router.post("/selection/batches/{batchId}/courses", summary="新增可选课程")
def sel_course_add(body: SelectionCourseBody, batchId: int = Path(...),
                   user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.add_course(user, batchId, body), message="已添加")


@router.get("/selection/batches/{batchId}/courses", summary="批次课程供给列表")
def sel_course_list(batchId: int = Path(...), page: int = 1, pageSize: int = 50,
                    user=Depends(require_permission(_SEL_VIEW))):
    items, total = selection_svc.list_courses(user, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.put("/selection/courses/{courseId}", summary="编辑容量/下限")
def sel_course_update(body: SelectionCourseUpdate, courseId: int = Path(...),
                      user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.update_course(user, courseId, body), message="已保存")


@router.post("/selection/courses/{courseId}/cancel", summary="人工取消开课（人数不足）")
def sel_course_cancel(courseId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.cancel_course(user, courseId), message="已取消开课")


@router.get("/selection/courses/{courseId}/roster", summary="选课名单（教师按授课关系收敛）")
def sel_course_roster(courseId: int = Path(...), page: int = 1, pageSize: int = 50,
                      user=Depends(require_permission(_SEL_ROSTER))):
    items, total = selection_svc.course_roster(user, courseId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ── 学生端 ──
@router.get("/selection/student/courses", summary="学生端可选课程+实时余量")
def sel_student_courses(batchId: Optional[str] = None, user=Depends(_require_student)):
    return success({"items": selection_svc.student_courses(user, batchId)})


@router.post("/selection/student/enroll", summary="学生选课（八条校验+行锁扣减）")
def sel_student_enroll(body: EnrollBody, user=Depends(_require_student)):
    return success(selection_svc.student_enroll(user, body), message="选课成功")


@router.post("/selection/student/drop", summary="学生退课")
def sel_student_drop(body: EnrollBody, user=Depends(_require_student)):
    return success(selection_svc.student_drop(user, body), message="退课成功")


@router.get("/selection/student/my", summary="我的选课记录")
def sel_student_my(batchId: Optional[str] = None, user=Depends(_require_student)):
    return success({"items": selection_svc.my_selections(user, batchId)})


# ── 教务处调整 / 补选 / 统计 ──
@router.post("/selection/records/{recordId}/adjust", summary="LOCKED 后人工调整退课（原因≥5字）")
def sel_record_adjust(body: AdjustBody, recordId: int = Path(...),
                      user=Depends(require_permission(_SEL_ADJUST))):
    return success(selection_svc.adjust_record(user, recordId, body.reason), message="已调整")


@router.get("/selection/batches/{batchId}/reselect-guide", summary="补选指引（CLOSED 批次）")
def sel_reselect_guide(batchId: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.reselect_guide(user, batchId))


@router.get("/selection/batches/{batchId}/stats", summary="选课统计")
def sel_stats(batchId: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.batch_stats(user, batchId))


@router.post("/selection/time-tick", summary="定时触发：到点自动开选/截止（供 cron 调度，幂等）")
def sel_time_tick(user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.run_time_tick(user), message="已执行时间触发")


# ══════════════ 考务管理（13B-SM-10，/academic-affairs/exam/*、/deferred-exams*） ══════════════
_EXAM_MANAGE = "academicAffairs.exam.manage"
_EXAM_ARRANGE = "academicAffairs.exam.arrange"
_EXAM_PUBLISH = "academicAffairs.exam.publish"
_EXAM_VIEW = "academicAffairs.exam.view"
_EXAM_ABNORMAL = "academicAffairs.exam.recordAbnormal"
_DEFER_COUNSELOR = "academicAffairs.deferredExam.counselorReview"
_DEFER_REVIEW = "academicAffairs.deferredExam.review"


class ExamBatchBody(BaseModel):
    batchName: str = Field(..., min_length=1)
    termId: Optional[str] = None
    examType: Optional[str] = "FINAL"
    examWeekStart: Optional[int] = None
    examWeekEnd: Optional[int] = None
    collegeScope: Optional[dict] = None


class ExamCourseBody(BaseModel):
    teachingTaskId: str = Field(..., min_length=1)


class ExamConfirmBody(BaseModel):
    action: str = Field(..., description="CONFIRM/REMOVE")


class ExamScheduleBody(BaseModel):
    examDate: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    durationMinutes: Optional[int] = None


class ExamRoomBody(BaseModel):
    classroomText: Optional[str] = None
    capacity: int = Field(0, ge=0)
    seatMode: Optional[str] = "SEQUENTIAL"


class SeatAssignBody(BaseModel):
    studentIds: list[str] = Field(default_factory=list)


class InvigilatorBody(BaseModel):
    teacherKey: str = Field(..., min_length=1)
    teacherName: Optional[str] = None
    role: Optional[str] = "ASSISTANT"


class IncidentBody(BaseModel):
    examCourseId: str = Field(..., min_length=1)
    studentId: str = Field(..., min_length=1)
    incidentType: str = Field(..., description="ABSENT/DISCIPLINE_VIOLATION/OTHER")
    description: Optional[str] = None


class DeferApplyBody(BaseModel):
    examCourseId: str = Field(..., min_length=1)
    reasonType: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=500)


class DeferReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/RETURN/REJECT")
    reason: Optional[str] = Field("", max_length=500)


# batch
@router.post("/exam/batches", summary="建考试批次")
def exam_batch_create(body: ExamBatchBody, user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.create_batch(user, body), message="已创建")


@router.get("/exam/batches", summary="考试批次列表")
def exam_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                 user=Depends(require_permission(_EXAM_VIEW))):
    items, total = exam_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/exam/batches/{bid}", summary="批次详情")
def exam_batch_detail(bid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success(exam_svc.get_batch(user, bid))


@router.post("/exam/batches/{bid}/courses", summary="圈定考试课程（从教学任务）")
def exam_course_add(body: ExamCourseBody, bid: int = Path(...), user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.add_exam_course(user, bid, body), message="已圈定")


@router.get("/exam/batches/{bid}/courses", summary="批次考试课程列表")
def exam_courses(bid: int = Path(...), page: int = 1, pageSize: int = 100, user=Depends(require_permission(_EXAM_VIEW))):
    items, total = exam_svc.list_courses(user, bid, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/exam/courses/{cid}/confirm", summary="学院确认/退回考试课程")
def exam_course_confirm(body: ExamConfirmBody, cid: int = Path(...), user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.confirm_course(user, cid, body.action), message="已处理")


@router.put("/exam/courses/{cid}/schedule", summary="设置考试时间/时长")
def exam_course_schedule(body: ExamScheduleBody, cid: int = Path(...), user=Depends(require_permission(_EXAM_ARRANGE))):
    return success(exam_svc.set_course_schedule(user, cid, body), message="已保存")


@router.post("/exam/batches/{bid}/confirm-courses", summary="课程确认完成，推进 DRAFT→COURSE_CONFIRMED")
def exam_confirm_courses(bid: int = Path(...), user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.confirm_batch_courses(user, bid), message="已推进")


# room / seats
@router.post("/exam/courses/{cid}/rooms", summary="添加考场")
def exam_room_add(body: ExamRoomBody, cid: int = Path(...), user=Depends(require_permission(_EXAM_ARRANGE))):
    return success(exam_svc.add_room(user, cid, body), message="已添加")


@router.get("/exam/courses/{cid}/rooms", summary="考场列表")
def exam_rooms(cid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success({"items": exam_svc.list_rooms(user, cid)})


@router.post("/exam/rooms/{roomId}/seats", summary="一键铺位（按学号/随机）")
def exam_seats_assign(body: SeatAssignBody, roomId: int = Path(...), user=Depends(require_permission(_EXAM_ARRANGE))):
    return success(exam_svc.assign_seats(user, roomId, body.studentIds), message="已铺位")


@router.get("/exam/rooms/{roomId}/seats", summary="座位表")
def exam_seats(roomId: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success({"items": exam_svc.room_seats(user, roomId)})


# invigilator
@router.post("/exam/rooms/{roomId}/invigilators", summary="指定监考（同时段冲突409）")
def exam_invig_add(body: InvigilatorBody, roomId: int = Path(...), user=Depends(require_permission(_EXAM_ARRANGE))):
    return success(exam_svc.assign_invigilator(user, roomId, body.teacherKey, body.teacherName, body.role), message="已指定")


@router.get("/exam/rooms/{roomId}/invigilators", summary="监考列表")
def exam_invigs(roomId: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success({"items": exam_svc.list_invigilators(user, roomId)})


class PatrolBody(BaseModel):
    teacherKey: str = Field(..., min_length=1)
    teacherName: Optional[str] = None
    patrolDate: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    areaScope: Optional[str] = None


@router.post("/exam/batches/{bid}/patrols", summary="排巡考（同时段/与监考冲突409）")
def exam_patrol_add(body: PatrolBody, bid: int = Path(...), user=Depends(require_permission(_EXAM_ARRANGE))):
    return success(exam_svc.assign_patrol(user, bid, body.teacherKey, body.teacherName,
                                          body.patrolDate, body.startTime, body.endTime, body.areaScope), message="已排巡考")


@router.get("/exam/batches/{bid}/patrols", summary="巡考列表")
def exam_patrols(bid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success({"items": exam_svc.list_patrols(user, bid)})


# publish / finish / archive
@router.post("/exam/batches/{bid}/publish", summary="发布批次（通知考生+监考）")
def exam_publish(bid: int = Path(...), user=Depends(require_permission(_EXAM_PUBLISH))):
    return success(exam_svc.publish_batch(user, bid), message="已发布")


@router.post("/exam/batches/{bid}/finish", summary="结束考试")
def exam_finish(bid: int = Path(...), user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.finish_batch(user, bid), message="已结束")


@router.post("/exam/batches/{bid}/archive", summary="归档批次")
def exam_archive(bid: int = Path(...), user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.archive_batch(user, bid), message="已归档")


# incidents
@router.post("/exam/incidents", summary="登记考场异常（缺考触发风险）")
def exam_incident_record(body: IncidentBody, user=Depends(require_permission(_EXAM_ABNORMAL))):
    return success(exam_svc.record_incident(user, body), message="已登记")


@router.get("/exam/incidents", summary="考场异常记录列表")
def exam_incidents(batchId: Optional[str] = None, page: int = 1, pageSize: int = 50,
                   user=Depends(require_permission(_EXAM_VIEW))):
    items, total = exam_svc.list_incidents(user, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/exam/batches/{bid}/stats", summary="考务统计")
def exam_stats(bid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success(exam_svc.batch_stats(user, bid))


# deferred exam
@router.post("/deferred-exams", summary="学生申请缓考")
def defer_apply(body: DeferApplyBody, user=Depends(_require_student)):
    return success(exam_svc.defer_apply(user, body), message="缓考申请已提交")


@router.get("/deferred-exams/my", summary="我的缓考申请")
def defer_my(status: Optional[str] = None, user=Depends(_require_student)):
    items, total = exam_svc.defer_list(user, status, student_only=True)
    return success(paginate(items, total, 1, len(items) or 1))


@router.post("/deferred-exams/{deferId}/resubmit", summary="退回后补材料重提")
def defer_resubmit(deferId: int = Path(...), user=Depends(_require_student)):
    return success(exam_svc.defer_resubmit(user, deferId), message="已重提")


@router.get("/deferred-exams", summary="缓考审批列表（教务/学院/教师/辅导员）")
def defer_list(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
               user=Depends(require_any_permission(_DEFER_COUNSELOR, _DEFER_REVIEW, "academicAffairs.exam.view"))):
    items, total = exam_svc.defer_list(user, status, student_only=False, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/deferred-exams/{deferId}/counselor-review", summary="缓考辅导员首级审批")
def defer_counselor_review(body: DeferReviewBody, deferId: int = Path(...),
                           user=Depends(require_permission(_DEFER_COUNSELOR))):
    return success(exam_svc.defer_review(user, deferId, body.action, body.reason), message="已处理")


@router.post("/deferred-exams/{deferId}/review", summary="缓考教师/学院/教务处审批")
def defer_review(body: DeferReviewBody, deferId: int = Path(...),
                 user=Depends(require_permission(_DEFER_REVIEW))):
    return success(exam_svc.defer_review(user, deferId, body.action, body.reason), message="已处理")


# ══════════════ 补考重修缓考免修（13B-SM-12，/academic-affairs/makeup|retake|exemption/*） ══════════════
_MK_MANAGE = "academicAffairs.makeup.manage"
_MK_VIEW = "academicAffairs.makeup.view"
_RT_APPLY = "academicAffairs.retake.apply"
_RT_REVIEW = "academicAffairs.retake.review"
_EX_REVIEW = "academicAffairs.exemption.review"


class MakeupBatchBody(BaseModel):
    batchName: str = Field(..., min_length=1)
    termCode: Optional[str] = None
    examBatchRef: Optional[str] = None


class MakeupEnrollBody(BaseModel):
    acadStudentId: str = Field(..., min_length=1)
    courseName: str = Field(..., min_length=1)
    originScore: Optional[int] = None


class MakeupScoreBody(BaseModel):
    score: int = Field(..., ge=0, le=100)


class RetakeApplyBody(BaseModel):
    courseName: str = Field(..., min_length=1)
    termCode: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=500)


class RetakeReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    reason: Optional[str] = Field("", max_length=500)


class RetakeEnrollBody(BaseModel):
    teachingTaskRef: Optional[str] = None


class ExemptionApplyBody(BaseModel):
    courseName: str = Field(..., min_length=1)
    termCode: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=500)
    materialFileIds: Optional[str] = None


class ExemptionReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/RETURN/REJECT")
    reason: Optional[str] = Field("", max_length=500)


class MergeDeferredBody(BaseModel):
    batchId: str = Field(..., min_length=1)


# ── 补考 ──
@router.get("/makeup/pending", summary="补考候选名单（成绩发布后不及格）")
def makeup_pending(term: Optional[str] = None, page: int = 1, pageSize: int = 50,
                   user=Depends(require_permission(_MK_VIEW))):
    items, total = makeup_svc.makeup_pending(user, term, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/makeup/batches", summary="建补考批次")
def makeup_batch_create(body: MakeupBatchBody, user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.create_makeup_batch(user, body), message="已创建")


@router.get("/makeup/batches", summary="补考批次列表")
def makeup_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                   user=Depends(require_permission(_MK_VIEW))):
    items, total = makeup_svc.list_makeup_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/makeup/batches/{bid}/enroll", summary="纳入补考名单")
def makeup_enroll(body: MakeupEnrollBody, bid: int = Path(...), user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.enroll_makeup(user, bid, body.acadStudentId, body.courseName, body.originScore), message="已纳入")


@router.post("/makeup/batches/{bid}/publish", summary="发布补考批次")
def makeup_publish(bid: int = Path(...), user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.publish_makeup_batch(user, bid), message="已发布")


@router.post("/makeup/records/{mid}/score", summary="录入补考成绩")
def makeup_score(body: MakeupScoreBody, mid: int = Path(...), user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.enter_makeup_score(user, mid, body.score), message="已录入")


@router.post("/makeup/batches/{bid}/college-review", summary="补考成绩学院审核（接R1审核链，SCORING→REVIEWED）")
def makeup_college_review(bid: int = Path(...), user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.college_review_scores(user, bid), message="学院审核通过")


@router.post("/makeup/batches/{bid}/finish", summary="教务发布回写（REVIEWED→FINISHED，接R1审核链末端）")
def makeup_finish(bid: int = Path(...), user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.finish_makeup_batch(user, bid), message="已发布回写")


class MakeupLinkExamBody(BaseModel):
    examBatchId: str = Field(..., min_length=1)


@router.post("/makeup/batches/{bid}/link-exam", summary="补考批次挂考务批次编排")
def makeup_link_exam(body: MakeupLinkExamBody, bid: int = Path(...), user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.link_exam_batch(user, bid, body.examBatchId), message="已挂考务编排")


# ── 重修 ──
@router.post("/retake/apply", summary="学生重修报名（次数上限校验）")
def retake_apply(body: RetakeApplyBody, user=Depends(_require_student)):
    return success(makeup_svc.retake_apply(user, body), message="重修报名已提交")


@router.get("/retake/my", summary="我的重修申请")
def retake_my(status: Optional[str] = None, user=Depends(_require_student)):
    items, total = makeup_svc.retake_list(user, status, student_only=True)
    return success(paginate(items, total, 1, len(items) or 1))


@router.get("/retake/applies", summary="重修申请审批列表")
def retake_applies(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                   user=Depends(require_permission(_RT_REVIEW))):
    items, total = makeup_svc.retake_list(user, status, student_only=False, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/retake/applies/{aid}/review", summary="重修教务处审批")
def retake_review(body: RetakeReviewBody, aid: int = Path(...), user=Depends(require_permission(_RT_REVIEW))):
    return success(makeup_svc.retake_review(user, aid, body.action, body.reason), message="已处理")


@router.post("/retake/applies/{aid}/enroll", summary="重修编入跟班")
def retake_enroll(body: RetakeEnrollBody, aid: int = Path(...), user=Depends(require_permission(_RT_REVIEW))):
    return success(makeup_svc.retake_enroll(user, aid, body.teachingTaskRef), message="已编入")


# ── 免修（三级审批） ──
@router.post("/exemption/apply", summary="学生免修申请（已获成绩422+每学期上限）")
def exemption_apply(body: ExemptionApplyBody, user=Depends(_require_student)):
    return success(makeup_svc.exemption_apply(user, body), message="免修申请已提交")


@router.get("/exemption/my", summary="我的免修申请")
def exemption_my(status: Optional[str] = None, user=Depends(_require_student)):
    items, total = makeup_svc.exemption_list(user, status, student_only=True)
    return success(paginate(items, total, 1, len(items) or 1))


@router.get("/exemption/applies", summary="免修审批列表（教师/学院/教务处）")
def exemption_applies(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                      user=Depends(require_permission(_EX_REVIEW))):
    items, total = makeup_svc.exemption_list(user, status, student_only=False, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/exemption/applies/{eid}/review", summary="免修三级审批")
def exemption_review(body: ExemptionReviewBody, eid: int = Path(...), user=Depends(require_permission(_EX_REVIEW))):
    return success(makeup_svc.exemption_review(user, eid, body.action, body.reason), message="已处理")


# ── 缓考合流 ──
@router.get("/makeup/deferred-pool", summary="缓考 APPROVED 学生池（供并入补考批次）")
def deferred_pool(page: int = 1, pageSize: int = 50, user=Depends(require_permission(_MK_VIEW))):
    items, total = makeup_svc.deferred_pool(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/makeup/deferred-pool/{did}/merge", summary="缓考并入补考批次")
def deferred_merge(body: MergeDeferredBody, did: int = Path(...), user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.merge_deferred(user, did, int(body.batchId)), message="已并入")


# ── 统计 ──
@router.get("/makeup/stats", summary="补考重修免修统计")
def makeup_stats(user=Depends(require_permission(_MK_VIEW))):
    mb, mbt = makeup_svc.list_makeup_batches(user, None, 1, 1000)
    rt, rtt = makeup_svc.retake_list(user, None, False, 1, 1000)
    ex, ext = makeup_svc.exemption_list(user, None, False, 1, 1000)
    return success({"makeupBatchCount": mbt, "retakeApplyCount": rtt, "exemptionApplyCount": ext,
                    "retakeApproved": len([r for r in rt if r["status"] in ("APPROVED", "ENROLLED", "FINISHED")]),
                    "exemptionApproved": len([e for e in ex if e["status"] == "APPROVED"])})


# ══════════════ 教材管理（13B，/academic-affairs/textbooks/*） ══════════════
_TB_CATALOG = "academicAffairs.textbook.catalog.manage"
_TB_SELECTION = "academicAffairs.textbook.selection.manage"
_TB_REVIEW = "academicAffairs.textbook.review.manage"
_TB_ORDER = "academicAffairs.textbook.order.manage"
_TB_DIST = "academicAffairs.textbook.distribution.manage"
_TB_FEE = "academicAffairs.textbook.fee.manage"
_TB_VIEW = "academicAffairs.textbook.view"


class TextbookBody(BaseModel):
    name: str = Field(..., min_length=1)
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    unitPrice: Optional[float] = None
    isNationalStandard: Optional[bool] = False
    status: Optional[str] = None


class SelectionBody(BaseModel):
    taskId: str = Field(..., min_length=1)
    textbookId: str = Field(..., min_length=1)
    expectedQty: Optional[int] = None
    remark: Optional[str] = None


class ReviewBatchBody(BaseModel):
    batchName: Optional[str] = None
    termId: Optional[str] = None
    selectionIds: list[str] = Field(default_factory=list)


class ReviewAdvanceBody(BaseModel):
    action: str = Field(..., description="APPROVE/RETURN")
    reason: Optional[str] = Field("", max_length=500)


class OrderBatchBody(BaseModel):
    batchName: Optional[str] = None
    termId: Optional[str] = None


class ArrivalBody(BaseModel):
    arrivedQty: int = Field(..., ge=0)


class DistGenerateBody(BaseModel):
    orderBatchId: str = Field(..., min_length=1)
    classId: Optional[str] = None
    studentIds: list[str] = Field(default_factory=list)


class FeeMarkBody(BaseModel):
    action: str = Field(..., description="PAID/PARTIAL/WAIVE")
    amount: Optional[float] = Field(None, ge=0, description="PARTIAL 部分收款金额")
    waiveReason: Optional[str] = Field("", max_length=500)


# ── 目录 ──
@router.post("/textbooks", summary="新增教材目录")
def textbook_create(body: TextbookBody, user=Depends(require_permission(_TB_CATALOG))):
    return success(textbook_svc.create_textbook(user, body), message="已创建")


@router.get("/textbooks", summary="教材目录列表")
def textbooks(keyword: Optional[str] = None, status: Optional[str] = None, page: int = 1, pageSize: int = 20,
              user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_svc.list_textbooks(user, keyword, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.put("/textbooks/{tid}", summary="编辑教材目录")
def textbook_update(body: TextbookBody, tid: int = Path(...), user=Depends(require_permission(_TB_CATALOG))):
    return success(textbook_svc.update_textbook(user, tid, body), message="已保存")


# ── 选用 ──
@router.post("/textbooks/selections", summary="按教学任务申报选用")
def selection_create(body: SelectionBody, user=Depends(require_permission(_TB_SELECTION))):
    return success(textbook_svc.create_selection(user, body), message="已创建")


@router.get("/textbooks/selections", summary="选用列表")
def selections(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
               user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_svc.list_selections(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/textbooks/selections/{sid}/submit", summary="提交选用")
def selection_submit(sid: int = Path(...), user=Depends(require_permission(_TB_SELECTION))):
    return success(textbook_svc.submit_selection(user, sid), message="已提交")


@router.post("/textbooks/selections/{sid}/withdraw", summary="撤回选用（仅草稿）")
def selection_withdraw(sid: int = Path(...), user=Depends(require_permission(_TB_SELECTION))):
    return success(textbook_svc.withdraw_selection(user, sid), message="已撤回")


# ── 审核 ──
@router.post("/textbooks/review-batches", summary="创建教材审核批次")
def review_create(body: ReviewBatchBody, user=Depends(require_permission(_TB_REVIEW))):
    return success(textbook_svc.create_review_batch(user, body), message="已创建")


@router.get("/textbooks/review-batches", summary="审核批次列表")
def review_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                   user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_svc.list_review_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/textbooks/review-batches/{bid}/advance", summary="审核推进（学院→教务→备案公示）")
def review_advance(body: ReviewAdvanceBody, bid: int = Path(...), user=Depends(require_permission(_TB_REVIEW))):
    return success(textbook_svc.review_batch_advance(user, bid, body.action, body.reason), message="已处理")


# ── 征订 ──
@router.post("/textbooks/order-batches", summary="从已备案选用生成征订批次")
def order_create(body: OrderBatchBody, user=Depends(require_permission(_TB_ORDER))):
    return success(textbook_svc.create_order_batch(user, body), message="已生成")


@router.get("/textbooks/order-batches", summary="征订批次列表")
def order_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                  user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_svc.list_order_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/textbooks/order-batches/{bid}/items", summary="征订明细")
def order_batch_items(bid: int = Path(...), user=Depends(require_permission(_TB_VIEW))):
    return success({"items": textbook_svc.order_items(user, bid)})


@router.post("/textbooks/order-batches/{bid}/submit", summary="提交征订")
def order_submit(bid: int = Path(...), user=Depends(require_permission(_TB_ORDER))):
    return success(textbook_svc.submit_order(user, bid), message="已提交")


@router.post("/textbooks/order-items/{itemId}/arrival", summary="登记到货")
def order_arrival(body: ArrivalBody, itemId: int = Path(...), user=Depends(require_permission(_TB_ORDER))):
    return success(textbook_svc.record_arrival(user, itemId, body.arrivedQty), message="已登记")


@router.post("/textbooks/order-batches/{bid}/archive", summary="归档征订批次")
def order_archive(bid: int = Path(...), user=Depends(require_permission(_TB_ORDER))):
    return success(textbook_svc.archive_order_batch(user, bid), message="已归档")


# ── 发放 ──
@router.post("/textbooks/distribution-batches", summary="生成发放名单（按班级+征订批次）")
def dist_generate(body: DistGenerateBody, user=Depends(require_permission(_TB_DIST))):
    return success(textbook_svc.generate_distribution(user, int(body.orderBatchId), body.classId, body.studentIds), message="已生成")


@router.get("/textbooks/distribution-batches/{bid}/records", summary="发放明细")
def dist_records(bid: int = Path(...), page: int = 1, pageSize: int = 100, user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_svc.list_distribution_records(user, bid, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/textbooks/distribution-records/{rid}/sign", summary="登记签收（触发费用台账）")
def dist_sign(rid: int = Path(...), user=Depends(require_permission(_TB_DIST))):
    return success(textbook_svc.sign_receipt(user, rid), message="已签收")


# ── 费用 ──
@router.get("/textbooks/fee-ledger", summary="教材费用台账")
def fee_ledger(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
               user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_svc.list_fees(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/textbooks/fee-ledger/{fid}/mark", summary="标记已收/部分收款/减免")
def fee_mark(body: FeeMarkBody, fid: int = Path(...), user=Depends(require_permission(_TB_FEE))):
    return success(textbook_svc.mark_fee(user, fid, body.action, body.amount, body.waiveReason), message="已处理")


@router.get("/textbooks/stock", summary="教材库存（到货量-已发放签收量）")
def textbook_stock(user=Depends(require_permission(_TB_VIEW))):
    return success({"items": textbook_svc.textbook_stock(user)})


# ── 统计 ──
@router.get("/textbooks/stats", summary="教材统计（征订/到货率/欠费）")
def textbook_stats(user=Depends(require_permission(_TB_VIEW))):
    return success(textbook_svc.stats(user))


# ══════════════ 排课管理增强（13B-SM-07，/academic-affairs/scheduling/*） ══════════════
_SCHED_RULE = "academicAffairs.schedule.rule.manage"
_SCHED_AVAIL = "academicAffairs.schedule.availability.manage"
_SCHED_VIEW = "academicAffairs.schedule.view"


class SchedRuleBody(BaseModel):
    ruleKey: str = Field(..., min_length=1)
    termId: Optional[str] = None
    batchId: Optional[str] = None
    ruleValue: Optional[dict] = None
    remark: Optional[str] = None


class AvailabilityBody(BaseModel):
    termId: Optional[str] = None
    weekday: int = Field(..., ge=1, le=7)
    slotNo: int = Field(..., ge=1)
    reason: Optional[str] = None


class AvailReviewBody(BaseModel):
    action: str = Field(..., description="ADOPT/REJECT")
    reason: Optional[str] = Field("", max_length=300)


# ── 排课规则中心 ──
@router.put("/scheduling/rules", summary="保存排课规则")
def sched_rule_save(body: SchedRuleBody, user=Depends(require_permission(_SCHED_RULE))):
    return success(scheduling_svc.save_rule(user, body), message="已保存")


@router.get("/scheduling/rules", summary="排课规则列表")
def sched_rules(termId: Optional[str] = None, batchId: Optional[str] = None,
                user=Depends(require_permission(_SCHED_VIEW))):
    return success({"items": scheduling_svc.list_rules(user, termId, batchId)})


@router.delete("/scheduling/rules/{ruleId}", summary="删除排课规则")
def sched_rule_delete(ruleId: int = Path(...), user=Depends(require_permission(_SCHED_RULE))):
    return success(scheduling_svc.delete_rule(user, ruleId), message="已删除")


# ── 教师可用时间 ──
@router.post("/scheduling/teacher-availability", summary="教师提交不可排课时段")
def sched_avail_submit(body: AvailabilityBody, user=Depends(require_staff)):
    return success(scheduling_svc.submit_availability(user, body), message="已提交")


@router.get("/scheduling/teacher-availability/my", summary="我提交的可用时间")
def sched_avail_my(termId: Optional[str] = None, user=Depends(require_staff)):
    return success({"items": scheduling_svc.list_availability(user, termId, mine=True)})


@router.get("/scheduling/teacher-availability", summary="教师可用时间汇总（学院采纳）")
def sched_avail_list(termId: Optional[str] = None, teacherKey: Optional[str] = None,
                     status: Optional[str] = None, user=Depends(require_permission(_SCHED_AVAIL))):
    return success({"items": scheduling_svc.list_availability(user, termId, teacherKey, status)})


@router.post("/scheduling/teacher-availability/{aid}/review", summary="采纳/驳回教师可用时间")
def sched_avail_review(body: AvailReviewBody, aid: int = Path(...), user=Depends(require_permission(_SCHED_AVAIL))):
    return success(scheduling_svc.review_availability(user, aid, body.action, body.reason), message="已处理")


# ── 全量冲突报告 ──
@router.get("/scheduling/batches/{bid}/conflict-report", summary="批次全量冲突报告（HARD/SOFT 分级）")
def sched_conflict_report(bid: int = Path(...), user=Depends(require_permission(_SCHED_VIEW))):
    return success(scheduling_svc.conflict_report(user, bid))


# ══════════════ 教学评价（13B，/academic-affairs/evaluation/*） ══════════════
_EVAL_MANAGE = "academicAffairs.evaluation.batch.manage"
_EVAL_VIEW = "academicAffairs.evaluation.view"
_EVAL_APPEAL = "academicAffairs.evaluation.appeal.review"


class EvalBatchBody(BaseModel):
    batchName: str = Field(..., min_length=1)
    termId: Optional[str] = None
    scope: Optional[dict] = None
    template: Optional[dict] = None
    anonymous: Optional[bool] = True


class EvalGenTasksBody(BaseModel):
    teachingTaskIds: list[str] = Field(default_factory=list)


class EvalSubmitBody(BaseModel):
    taskId: str = Field(..., min_length=1)
    answers: Optional[dict] = None
    objectiveScore: Optional[float] = Field(None, ge=0, le=100)
    comment: Optional[str] = Field(None, max_length=1000)


class EvalAppealBody(BaseModel):
    resultId: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=5, max_length=1000)


class EvalAppealReviewBody(BaseModel):
    action: str = Field(..., description="RESOLVE/REJECT")
    reason: Optional[str] = Field("", max_length=1000)


# ── 批次 ──
@router.post("/evaluation/batches", summary="建评教批次")
def eval_batch_create(body: EvalBatchBody, user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.create_batch(user, body), message="已创建")


@router.get("/evaluation/batches", summary="评教批次列表")
def eval_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                 user=Depends(require_permission(_EVAL_VIEW))):
    items, total = evaluation_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/evaluation/batches/{bid}", summary="批次详情")
def eval_batch_detail(bid: int = Path(...), user=Depends(require_permission(_EVAL_VIEW))):
    return success(evaluation_svc.get_batch(user, bid))


@router.post("/evaluation/batches/{bid}/tasks", summary="生成应评任务（挂教学任务）")
def eval_gen_tasks(body: EvalGenTasksBody, bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.generate_tasks(user, bid, body.teachingTaskIds), message="已生成")


@router.get("/evaluation/batches/{bid}/tasks", summary="应评任务列表")
def eval_tasks(bid: int = Path(...), evaluatorType: Optional[str] = None, user=Depends(require_permission(_EVAL_VIEW))):
    return success({"items": evaluation_svc.list_tasks(user, bid, evaluatorType)})


@router.post("/evaluation/batches/{bid}/publish", summary="发布批次")
def eval_publish(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.publish_batch(user, bid), message="已发布")


@router.post("/evaluation/batches/{bid}/open", summary="开放评教窗口")
def eval_open(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.open_batch(user, bid), message="已开放")


@router.post("/evaluation/batches/{bid}/close-score", summary="关闭核算（学生均分分级）")
def eval_close_score(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.close_and_score(user, bid), message="已核算")


@router.post("/evaluation/batches/{bid}/publish-results", summary="发布结果（教师可见本人）")
def eval_publish_results(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.publish_results(user, bid), message="已发布结果")


@router.post("/evaluation/batches/{bid}/archive", summary="归档批次")
def eval_archive(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.archive_batch(user, bid), message="已归档")


# ── 提交评价（学生匿名/教师自评/同行/督导） ──
@router.post("/evaluation/submit", summary="提交评价（学生匿名不存身份）")
def eval_submit(body: EvalSubmitBody, user=Depends(get_current_user)):
    return success(evaluation_svc.submit_evaluation(user, int(body.taskId), body.answers, body.objectiveScore, body.comment), message="已提交")


# ── 结果 / 申诉 / 统计 ──
@router.get("/evaluation/batches/{bid}/results", summary="评价结果（教务处全量）")
def eval_results(bid: int = Path(...), page: int = 1, pageSize: int = 50, user=Depends(require_permission(_EVAL_VIEW))):
    items, total = evaluation_svc.list_results(user, bid, mine=False, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/evaluation/batches/{bid}/my-results", summary="我的评价结果（教师本人，已发布）")
def eval_my_results(bid: int = Path(...), user=Depends(require_staff)):
    items, total = evaluation_svc.list_results(user, bid, mine=True)
    return success({"items": items})


@router.post("/evaluation/appeals", summary="教师对结果申诉")
def eval_appeal_submit(body: EvalAppealBody, user=Depends(require_staff)):
    return success(evaluation_svc.submit_appeal(user, int(body.resultId), body.reason), message="申诉已提交")


@router.get("/evaluation/appeals", summary="申诉列表")
def eval_appeals(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                 user=Depends(require_permission(_EVAL_APPEAL))):
    items, total = evaluation_svc.list_appeals(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/evaluation/appeals/{aid}/review", summary="申诉审核")
def eval_appeal_review(body: EvalAppealReviewBody, aid: int = Path(...), user=Depends(require_permission(_EVAL_APPEAL))):
    return success(evaluation_svc.review_appeal(user, aid, body.action, body.reason), message="已处理")


@router.get("/evaluation/batches/{bid}/stats", summary="评价统计")
def eval_stats(bid: int = Path(...), user=Depends(require_permission(_EVAL_VIEW))):
    return success(evaluation_svc.stats(user, bid))


# ══════════════ 教学质量（13B，零新表；/academic-affairs/quality/*） ══════════════
_QUALITY_VIEW = "academicAffairs.quality.dashboard.view"
_QUALITY_EXPORT = "academicAffairs.quality.report.export"


class QualityExportBody(BaseModel):
    termId: Optional[str] = None
    collegeId: Optional[str] = None
    majorId: Optional[str] = None
    purpose: str = Field(..., min_length=5, description="导出用途（≥5字，写审计）")


@router.get("/quality/dashboard", summary="教学质量指标看板（实时聚合既有表）")
def quality_dashboard(termId: Optional[str] = None, collegeId: Optional[str] = None,
                      majorId: Optional[str] = None, user=Depends(require_permission(_QUALITY_VIEW))):
    return success(quality_svc.dashboard(user, termId, collegeId, majorId))


@router.get("/quality/reports", summary="质量报告导出历史")
def quality_reports(page: int = 1, pageSize: int = 20, user=Depends(require_permission(_QUALITY_VIEW))):
    items, total = quality_svc.list_reports(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/quality/reports/export", summary="导出教务运行质量报告 xlsx")
def quality_report_export(body: QualityExportBody, user=Depends(require_permission(_QUALITY_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content = quality_svc.export_report(user, body.termId, body.collegeId, body.majorId, body.purpose)
    return StreamingResponse(io.BytesIO(content),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=academic_quality_report.xlsx"})


# ══════════════ 教务归档（13B-R7，/academic-affairs/archive/*） ══════════════
_ARCHIVE_MANAGE = "academicAffairs.archive.manage"
_ARCHIVE_VIEW = "academicAffairs.archive.view"


class ArchiveBatchBody(BaseModel):
    termId: Optional[str] = None
    batchName: Optional[str] = None


class ArchiveConfirmBody(BaseModel):
    force: bool = Field(False, description="MISSING_ITEMS 时强制归档")


class ArchiveUnfreezeBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


@router.post("/archive/batches", summary="建归档批次（按学期，一学期一批次）")
def archive_batch_create(body: ArchiveBatchBody, user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.create_batch(user, body), message="已创建")


@router.get("/archive/batches", summary="归档批次列表")
def archive_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                    user=Depends(require_permission(_ARCHIVE_VIEW))):
    items, total = archive_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/archive/batches/{bid}", summary="归档批次详情（含9数据域物料）")
def archive_batch_detail(bid: int = Path(...), user=Depends(require_permission(_ARCHIVE_VIEW))):
    return success(archive_svc.get_batch(user, bid))


@router.post("/archive/batches/{bid}/check", summary="完整性检查（聚合9数据域）")
def archive_check(bid: int = Path(...), user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.run_check(user, bid), message="已检查")


@router.post("/archive/batches/{bid}/confirm", summary="确认归档（学期封存 ARCHIVED）")
def archive_confirm(body: ArchiveConfirmBody = ArchiveConfirmBody(), bid: int = Path(...),
                    user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.confirm_archive(user, bid, body.force), message="已归档")


@router.post("/archive/batches/{bid}/unfreeze", summary="特批解冻（仅学校管理员）")
def archive_unfreeze(body: ArchiveUnfreezeBody, bid: int = Path(...),
                     user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.unfreeze(user, bid, body.reason), message="已解冻")


@router.post("/archive/batches/{bid}/cancel", summary="取消归档批次")
def archive_cancel(bid: int = Path(...), user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.cancel_batch(user, bid), message="已取消")
