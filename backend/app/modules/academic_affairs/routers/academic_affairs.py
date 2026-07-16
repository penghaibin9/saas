"""13B 教务中心 API（/api/v1/academic-affairs/*）—— P1：首页 + 学年学期/校历/节次 + 学籍名册 + 入学注册。"""
from __future__ import annotations

import io
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Path, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.exceptions import AppException
from app.core.permissions import enforce_permission, require_any_permission, require_permission
from app.core.response import paginate, success
from app.core.security import get_current_user, require_staff
from app.schemas.excel import ExcelErrorRows, ExcelImportRows
from app.services import xlsx_util

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _require_student(user: dict = Depends(get_current_user)) -> dict:
    """学生本人端点守卫：仅 userType=STUDENT（对齐项目约定——学生不进 PC 管理端权限点，走本人端点）。"""
    if (user.get("userType") or "").strip().upper() != "STUDENT":
        raise AppException("NO_PERMISSION", "仅学生本人可访问选课自助端点", http_status=403)
    return user
from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_svc
from app.modules.academic_affairs.services import academic_affairs_attendance_service as attendance_svc
from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as recheck_svc
from app.modules.academic_affairs.services import academic_affairs_workload_service as workload_svc
from app.modules.academic_affairs.services import academic_affairs_change_service as change_svc
from app.modules.academic_affairs.services import academic_affairs_course_service as course_svc
from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_svc
from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad_svc
from app.modules.academic_affairs.services import academic_affairs_org_service as org_svc
from app.modules.academic_affairs.services import academic_affairs_program_service as prog_svc
from app.modules.academic_affairs.services import academic_affairs_resource_service as resource_svc
from app.modules.academic_affairs.services import academic_affairs_autoexam_service as autoexam_svc
from app.modules.academic_affairs.services import academic_affairs_autoschedule_service as autosched_svc
from app.modules.academic_affairs.services import academic_affairs_level_exam_service as level_exam_svc
from app.modules.academic_affairs.services import academic_affairs_major_split_service as major_split_svc
from app.modules.academic_affairs.services import academic_affairs_recognition_service as recog_svc
from app.modules.academic_affairs.services import academic_affairs_selection_round_service as selection_round_svc
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


@router.get("/dashboard/reminders", summary="教务看板提醒聚合（成绩提交进度/考试安排/学籍异动/学业预警/毕业资格预警/教务待办"
                                             "/今日教学运行/今日课程/调停课提醒/教学资源占用/教务数据趋势）")
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


# ── 学年学期 Tier1-R2：当前学期设置 / 学期周次 / 教学周配置 / 学期状态 / 学期归档总览 ──
_TERM_VIEW = "academicAffairs.term.view"
_TERM_MANAGE = "academicAffairs.term.manage"


@router.post("/terms/{termId}/set-current", summary="当前学期设置：设为当前学期（仅 PUBLISHED，幂等）")
def term_set_current(termId: int = Path(...), user=Depends(require_permission(_TERM_MANAGE))):
    return success(svc.set_current_term(termId, user), message="已设为当前学期")


@router.get("/terms/{termId}/weeks", summary="学期周次（按开学日+教学周展开，叠加校历事件）")
def term_weeks(termId: int = Path(...), user=Depends(require_permission(_TERM_VIEW))):
    return success({"items": svc.list_term_weeks(termId, user)})


class TeachingWeeksBody(BaseModel):
    teachingWeeks: Optional[int] = Field(None, ge=1, le=30)
    examWeekStart: Optional[int] = Field(None, ge=1, le=30)


@router.put("/terms/{termId}/teaching-weeks", summary="教学周配置（仅 DRAFT 学期可调整结构）")
def term_teaching_weeks_update(body: TeachingWeeksBody, termId: int = Path(...),
                               user=Depends(require_permission(_TERM_MANAGE))):
    return success(svc.update_teaching_weeks(termId, body, user), message="已保存")


@router.post("/terms/{termId}/freeze", summary="学期状态·冻结（PUBLISHED→FROZEN）")
def term_freeze(termId: int = Path(...), user=Depends(require_permission(_TERM_MANAGE))):
    return success(svc.freeze_term(termId, user), message="已冻结")


class TermUnfreezeBody(BaseModel):
    reason: str = Field(..., min_length=1)


@router.post("/terms/{termId}/unfreeze", summary="学期状态·解冻（FROZEN→PUBLISHED，原因≥5字）")
def term_unfreeze(body: TermUnfreezeBody, termId: int = Path(...),
                  user=Depends(require_permission(_TERM_MANAGE))):
    return success(svc.unfreeze_term(termId, body.reason, user), message="已解冻")


@router.get("/terms/archive-overview", summary="学期归档总览（只读，实际归档动作见教务归档模块）")
def terms_archive_overview(user=Depends(require_permission(_TERM_VIEW))):
    return success({"items": svc.term_archive_overview(user)})


# ── 学年学期 续工 R3：学年管理（按学年汇总） / 学期切换记录（当前学期切换审计） ──
# 均为字面量路径，须注册在 /terms/{termId} 之前，规则同上（FastAPI 按声明顺序匹配路由）。
@router.get("/terms/years", summary="学年管理：按学年汇总学期（只读聚合，不新建表）")
def terms_years(user=Depends(require_permission(_TERM_VIEW))):
    return success({"items": svc.list_academic_years(user)})


@router.get("/terms/switch-log", summary="学期切换记录：当前学期切换审计（PUBLISH/SET_CURRENT 流水推导）")
def terms_switch_log(page: int = 1, pageSize: int = 50, user=Depends(require_permission(_TERM_VIEW))):
    items, total = svc.list_term_switch_log(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# 注：term_detail 的 {termId} 路径必须注册在上面的字面量路径 /terms/archive-overview 之后——
# FastAPI 按声明顺序匹配路由，{termId} 若先声明会把 "archive-overview" 当成 termId 抢先匹配，
# 导致归档总览端点 400（本条是总控合并复核发现并修复的真实路由顺序 bug，非文本冲突）。
@router.get("/terms/{termId}", summary="学期详情（校历/作息等只读联动查看复用）")
def term_detail(termId: int = Path(...), user=Depends(require_permission(_TERM_VIEW))):
    return success(svc.term_detail(termId, user))


# 注：校历节次 Tier1-R2 原设计的 POST /terms/{termId}/archive（直接改 AaTerm.status=ARCHIVED，
# 绕开教务归档模块的批次+9域完整性检查+正规解冻通道）已在总控合并复核时移除——该路径与教务归档模块的
# confirm_archive() 写同一字段但完全不做完整性校验，且当前代码库无任何方式撤销，会把一次"归档校历"
# 误操作变成永久锁死全模块 19+ 个写端点的不可逆事故。"校历归档"改为上面的 term_detail 只读展示 +
# 前端引导跳转教务归档模块正规流程（施工记录已登记，若确需窄语义的"仅锁校历"开关，
# 应走独立字段而非复用 AaTerm.status，见总控复核B报告）。


class CalendarEventBody(BaseModel):
    eventType: str = Field("TEACHING", description="TEACHING/EXAM/INTERNSHIP/HOLIDAY/SWAP")
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    swapToDate: Optional[str] = None
    remark: Optional[str] = None


class CalendarEventUpdate(BaseModel):
    eventType: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    swapToDate: Optional[str] = None
    remark: Optional[str] = None


@router.post("/terms/{termId}/calendar", summary="添加校历事件（节假日/补课日/教学/考试/实习）")
def calendar_add(body: CalendarEventBody, termId: int = Path(...),
                 user=Depends(require_permission("academicAffairs.calendar.manage"))):
    return success(svc.add_calendar_event(termId, user, body), message="已添加")


@router.get("/terms/{termId}/calendar", summary="校历事件列表（可按 eventType 过滤：HOLIDAY 节假日/SWAP 补课日）")
def calendar_list(termId: int = Path(...), eventType: Optional[str] = None,
                  user=Depends(require_permission("academicAffairs.calendar.view"))):
    return success({"items": svc.list_calendar(termId, user, eventType)})


@router.put("/terms/{termId}/calendar/{eventId}", summary="编辑校历事件（发布后锁定 409）")
def calendar_update(body: CalendarEventUpdate, termId: int = Path(...), eventId: int = Path(...),
                    user=Depends(require_permission("academicAffairs.calendar.manage"))):
    return success(svc.update_calendar_event(termId, eventId, user, body), message="已保存")


@router.delete("/terms/{termId}/calendar/{eventId}", summary="删除校历事件（发布后锁定 409）")
def calendar_delete(termId: int = Path(...), eventId: int = Path(...),
                    user=Depends(require_permission("academicAffairs.calendar.manage"))):
    return success(svc.delete_calendar_event(termId, eventId, user), message="已删除")


@router.get("/terms/{termId}/week-calendar", summary="教学周日历（周次×周类型聚合，叠加节假日/补课日着色）")
def week_calendar(termId: int = Path(...), user=Depends(require_permission("academicAffairs.calendar.view"))):
    return success(svc.week_calendar(termId, user))


@router.post("/terms/{termId}/calendar/publish", summary="发布校历（校验节次已配置+补课日已配对，仅教务处/学校管理员）")
def calendar_publish(termId: int = Path(...), user=Depends(require_permission("academicAffairs.calendarPublish.manage"))):
    return success(svc.publish_calendar(termId, user), message="已发布")


# ── 作息节次（节次管理，全校统一，不随学期锁定）──
class TimeSlotCreate(BaseModel):
    slotNo: int = Field(..., ge=1)
    slotName: Optional[str] = None
    startTime: Optional[str] = Field(None, description="HH:MM")
    endTime: Optional[str] = None


class TimeSlotUpdate(BaseModel):
    slotNo: Optional[int] = Field(None, ge=1)
    slotName: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    enabled: Optional[bool] = None


@router.post("/time-slots", summary="新建作息节次")
def time_slot_create(body: TimeSlotCreate, user=Depends(require_permission("academicAffairs.timeslot.manage"))):
    return success(svc.create_time_slot(body, user), message="已创建")


@router.get("/time-slots", summary="作息节次列表（includeDisabled=true 含已停用，供节次管理页）")
def time_slots(includeDisabled: bool = False, user=Depends(require_permission("academicAffairs.timeslot.view"))):
    return success({"items": svc.list_time_slots(user, includeDisabled)})


@router.put("/time-slots/{slotId}", summary="编辑作息节次（含启用/停用）")
def time_slot_update(body: TimeSlotUpdate, slotId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.timeslot.manage"))):
    return success(svc.update_time_slot(slotId, user, body), message="已保存")


@router.delete("/time-slots/{slotId}", summary="删除作息节次（逻辑删除）")
def time_slot_delete(slotId: int = Path(...), user=Depends(require_permission("academicAffairs.timeslot.manage"))):
    return success(svc.delete_time_slot(slotId, user), message="已删除")


# ── 上课时间段（节次的实际钟点，支持按校区/生效日期区间配置多套作息）──
class TimeBandCreate(BaseModel):
    bandName: Optional[str] = None
    campusCode: Optional[str] = None
    effectiveStart: Optional[str] = None
    effectiveEnd: Optional[str] = None
    startTime: str = Field(..., min_length=1, description="HH:MM")
    endTime: str = Field(..., min_length=1, description="HH:MM")


class TimeBandUpdate(BaseModel):
    bandName: Optional[str] = None
    campusCode: Optional[str] = None
    effectiveStart: Optional[str] = None
    effectiveEnd: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    status: Optional[str] = None


@router.post("/time-slots/{slotId}/time-bands", summary="新建上课时间段（绑定节次的实际钟点）")
def time_band_create(body: TimeBandCreate, slotId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.classTimeBand.manage"))):
    return success(svc.create_time_band(slotId, user, body), message="已创建")


@router.get("/time-slots/{slotId}/time-bands", summary="上课时间段列表（按节次）")
def time_band_list(slotId: int = Path(...), user=Depends(require_permission("academicAffairs.classTimeBand.view"))):
    return success({"items": svc.list_time_bands(slotId, user)})


@router.put("/time-bands/{bandId}", summary="编辑上课时间段")
def time_band_update(body: TimeBandUpdate, bandId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.classTimeBand.manage"))):
    return success(svc.update_time_band(bandId, user, body), message="已保存")


@router.delete("/time-bands/{bandId}", summary="删除上课时间段")
def time_band_delete(bandId: int = Path(...), user=Depends(require_permission("academicAffairs.classTimeBand.manage"))):
    return success(svc.delete_time_band(bandId, user), message="已删除")


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


# ── 学籍信息更正（Tier1 R3）：区别于「学籍异动」——只纠正学号/姓名/性别/证件号/年级录入错误，
# 不产生学籍状态迁移；单步审核（PENDING→APPROVED 同步主档 / REJECTED）。
_ROSTER_CORRECTION_APPLY = "academicAffairs.roster.correction.apply"
_ROSTER_CORRECTION_VIEW = "academicAffairs.roster.correction.view"
_ROSTER_CORRECTION_REVIEW = "academicAffairs.roster.correction.review"


class RosterCorrectionCreate(BaseModel):
    studentId: str = Field(..., min_length=1)
    fieldKey: str = Field(..., description="STUDENT_NO/REAL_NAME/GENDER/ID_CARD/GRADE")
    newValue: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=5, description="更正原因（≥5 字，必填，写审计）")
    materialFileIds: Optional[List[str]] = Field(
        None, description="证明材料 file_id 列表（先经 POST /api/v1/files/upload 上传）。"
                          "更正姓名/性别/证件号时**必填**且须户籍/公安部门出具——合规硬要求，"
                          "依据教职成〔2014〕12号第十六条、教育部令41号第三十四条；学号/年级选填。")


class RosterCorrectionReview(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    note: Optional[str] = Field("", max_length=500)


@router.post("/roster/corrections", summary="发起学籍信息更正（学号/姓名/性别/证件号/年级）")
def roster_correction_create(body: RosterCorrectionCreate, user=Depends(require_permission(_ROSTER_CORRECTION_APPLY))):
    return success(svc.create_roster_correction(user, body.studentId, body.fieldKey, body.newValue, body.reason,
                                                body.materialFileIds),
                   message="更正申请已提交")


@router.get("/roster/corrections", summary="学籍信息更正列表（范围过滤+敏感字段脱敏）")
def roster_correction_list(status: Optional[str] = None, studentId: Optional[str] = None,
                           fieldKey: Optional[str] = None, page: int = 1, pageSize: int = 20,
                           user=Depends(require_any_permission(_ROSTER_CORRECTION_VIEW, _ROSTER_CORRECTION_REVIEW))):
    items, total = svc.list_roster_corrections(user, status, studentId, fieldKey, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/roster/corrections/{correctionId}/review", summary="学籍信息更正审核（通过即同步主档/驳回）")
def roster_correction_review(body: RosterCorrectionReview, correctionId: int = Path(...),
                             user=Depends(require_permission(_ROSTER_CORRECTION_REVIEW))):
    return success(svc.review_roster_correction(correctionId, user, body.action, body.note), message="已处理")


# ── 入学/学年注册 ──
class RegBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    registerType: str = Field("ENROLL", description="ENROLL 入学 / ANNUAL 学年 / SEMESTER 学期")
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


# ── 注册归档（续工三级卡）：OPEN→CLOSED→ARCHIVED，仅教务处（TENANT_ALL，服务层 _require_school_scope 校验）──
_REG_ARCHIVE_VIEW = "academicAffairs.registration.archive.view"
_REG_ARCHIVE_MANAGE = "academicAffairs.registration.archive.manage"
_REG_ARCHIVE_EXPORT = "academicAffairs.registration.archive.export"


@router.post("/registration-batches/{batchId}/close", summary="关闭注册批次（OPEN→CLOSED，仅教务处）")
def reg_batch_close(batchId: int = Path(...), user=Depends(require_permission(_REG_ARCHIVE_MANAGE))):
    return success(svc.close_registration_batch(batchId, user), message="已关闭")


@router.post("/registration-batches/{batchId}/archive", summary="归档注册批次（CLOSED→ARCHIVED，仅教务处）")
def reg_batch_archive(batchId: int = Path(...), user=Depends(require_permission(_REG_ARCHIVE_MANAGE))):
    return success(svc.archive_registration_batch(batchId, user), message="已归档")


@router.get("/registration/archive", summary="注册归档：已归档批次列表")
def reg_archive_list(page: int = 1, pageSize: int = 20, user=Depends(require_permission(_REG_ARCHIVE_VIEW))):
    items, total = svc.list_archived_registration_batches(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/registration/archive/{batchId}", summary="注册归档批次详情（含注册完成统计）")
def reg_archive_detail(batchId: int = Path(...), user=Depends(require_permission(_REG_ARCHIVE_VIEW))):
    return success(svc.registration_archive_detail(batchId, user))


class RegArchiveExportBody(BaseModel):
    purpose: str = Field(..., min_length=5, description="导出用途（≥5 字，必填，写审计）")


@router.post("/registration/archive/{batchId}/export", summary="注册归档台账导出 xlsx（水印+审计）")
def reg_archive_export(body: RegArchiveExportBody, batchId: int = Path(...),
                       user=Depends(require_permission(_REG_ARCHIVE_EXPORT))):
    content = svc.export_registration_archive_xlsx(batchId, user, body.purpose)
    return StreamingResponse(
        io.BytesIO(content), media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": f"attachment; filename=registration_archive_{batchId}.xlsx"})


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
    changeType: str = Field(..., description="SUSPEND/RESUME/WITHDRAW/RETAIN/TRANSFER_MAJOR/TRANSFER_CLASS")
    reason: Optional[str] = Field("", max_length=500)
    toCollegeId: Optional[str] = None
    toMajorId: Optional[str] = None
    toClassId: Optional[str] = Field(None, description="TRANSFER_MAJOR/TRANSFER_CLASS 目标班级；TRANSFER_CLASS 必填")


class AaReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT/RETURN")
    reason: Optional[str] = Field("", max_length=500)


@router.post("/status-changes", summary="发起学籍异动（含休学/复学/退学/转专业/转班分类申请入口，changeType 区分）")
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


# ── 实践环节（集中性实践教学环节：认识实习/课程设计/顶岗实习/毕业设计等，以周计，Tier1 R3 续工） ──

class PracticeSegmentCreate(BaseModel):
    segmentName: str = Field(..., min_length=1)
    segmentType: Optional[str] = Field("OTHER", description="COGNITION_INTERNSHIP/COURSE_DESIGN/"
                                        "PRODUCTION_INTERNSHIP/POST_INTERNSHIP/GRADUATION_PROJECT/"
                                        "MILITARY_TRAINING/SOCIAL_PRACTICE/OTHER")
    openTermNo: Optional[int] = None
    weeks: Optional[float] = Field(None, gt=0)
    credit: Optional[float] = Field(None, ge=0)
    orgMode: Optional[str] = Field("CENTRALIZED", description="CENTRALIZED/DISTRIBUTED 集中/分散")
    location: Optional[str] = None
    assessmentMode: Optional[str] = Field("CHECK", description="EXAM/CHECK 考试/考查")
    sortOrder: Optional[int] = None


class PracticeSegmentUpdate(BaseModel):
    segmentName: Optional[str] = None
    segmentType: Optional[str] = None
    openTermNo: Optional[int] = None
    weeks: Optional[float] = Field(None, gt=0)
    credit: Optional[float] = Field(None, ge=0)
    orgMode: Optional[str] = None
    location: Optional[str] = None
    assessmentMode: Optional[str] = None
    sortOrder: Optional[int] = None


@router.get("/programs/{programId}/practice-segments", summary="实践环节：条目列表（集中性实践教学环节，编制态可写）")
def program_practice_segments(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_practice_segments(programId, user)})


@router.post("/programs/{programId}/practice-segments", summary="实践环节：新增条目（编制态）")
def program_practice_segment_create(body: PracticeSegmentCreate, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.create_practice_segment(programId, user, body), message="已添加")


@router.put("/programs/practice-segments/{segmentId}", summary="实践环节：编辑条目（编制态）")
def program_practice_segment_update(body: PracticeSegmentUpdate, segmentId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.update_practice_segment(segmentId, user, body), message="已保存")


@router.delete("/programs/practice-segments/{segmentId}", summary="实践环节：删除条目（编制态）")
def program_practice_segment_delete(segmentId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.delete_practice_segment(segmentId, user), message="已删除")


# ── 方案变更（状态生命周期：冻结/恢复/停用，原因必填，Tier1 R3 续工） ──

_PROG_CHANGE = require_permission("academicAffairs.program.changeStatus")


class ProgramChangeStatusBody(BaseModel):
    action: str = Field(..., description="FREEZE 冻结/RESUME 恢复/DISABLE 停用")
    reason: str = Field(..., min_length=5, max_length=500, description="变更原因，≥5字，写入审计留痕")


@router.post("/programs/{programId}/change-status", summary="方案变更：状态生命周期（FREEZE 冻结/RESUME 恢复/DISABLE 停用，原因必填）")
def program_change_status(body: ProgramChangeStatusBody, programId: int = Path(...), user=Depends(_PROG_CHANGE)):
    return success(prog_svc.change_program_status(programId, user, body.action, body.reason), message="已处理")


@router.get("/programs/{programId}/change-log", summary="方案变更：生命周期变更记录（冻结/恢复/停用/新建版本/退回）")
def program_change_log(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_program_lifecycle_log(programId, user)})


# ── 方案归档（只读：已停用方案 + 已被取代历史版本，Tier1 R3 续工） ──
# 顶层 kebab 资源名 /program-archive（而非 /programs/archive）：避免与上方 /programs/{programId} 的
# 单段路径匹配发生路由遮蔽（FastAPI/Starlette 按注册顺序做结构匹配，"archive" 会先被当作 programId 解析，
# 因非 int 类型触发 RequestValidationError，本仓库全局处理器统一转 400），与既有 /status-changes、
# /registration-batches 等顶层 kebab 资源命名一致。

@router.get("/program-archive", summary="方案归档：已停用方案 + 已被取代历史版本（只读）")
def programs_archived(page: int = 1, pageSize: int = 20, user=Depends(_PROG_VIEW)):
    items, total = prog_svc.list_archived_programs(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ── 计划变更（教务中心-教学计划「计划变更」收编入口，R3 新增）──
# 复用「方案版本」同一版本链机制（已发布/启用/冻结/停用方案改动强制新版本），区别仅在于本入口强制要求
# 变更原因（≥5字）并写专属审计事件 CHANGE_NEW_VERSION，供「计划变更」留痕追溯；不建独立表，零新迁移。

class ProgramChangeBody(BaseModel):
    reason: str = Field(..., min_length=1)


@router.post("/programs/{programId}/change", summary="计划变更：基于已发布/启用/冻结版本新建新版本并记录变更原因")
def program_change(body: ProgramChangeBody, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.create_new_version(programId, user, body.reason), message="变更已生效，已生成新版本")


# ═══════════ 课程库（P3，两级审核，商业级全字段）═══════════
# Tier1 R2（新增课程/课程分类/课程性质/学分学时/课程负责人/课程停用）：写操作从 require_staff 收紧为
# 精确 permissionCode（均命中 permissions.py 既有 "academicAffairs.*" 角色通配，不新增角色）。
_COURSE_VIEW = require_permission("academicAffairs.course.view")
_COURSE_MANAGE = require_permission("academicAffairs.course.manage")
_COURSE_APPROVE = require_permission("academicAffairs.course.approve")


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
    ownerTeacherId: Optional[str] = Field(None, description="课程负责人 userId（若提供须为本校在职教师）")
    isCore: bool = Field(False)
    description: Optional[str] = Field(None, description="课程简介，选填，≤500 字")
    applicableMajors: Optional[list] = Field(default_factory=list, description="适用专业 majorId 列表（与 isAllMajor 互斥）")
    isAllMajor: bool = Field(False, description="是否全校通用")
    prerequisiteCodes: Optional[list] = Field(default_factory=list)


@router.post("/courses", summary="新建课程（草稿）")
def course_create(body: CourseCreate, user=Depends(_COURSE_MANAGE)):
    return success(course_svc.create_course(body, user), message="已创建")


@router.get("/courses", summary="课程库列表")
def courses(keyword: Optional[str] = None, category: Optional[str] = None, nature: Optional[str] = None,
            status: Optional[str] = None, ownerTeacherId: Optional[str] = None, ownerCollegeId: Optional[str] = None,
            page: int = 1, pageSize: int = 20, user=Depends(_COURSE_VIEW)):
    items, total = course_svc.list_courses(user, keyword, category, nature, status, page, pageSize,
                                           owner_teacher_id=ownerTeacherId, owner_college_id=ownerCollegeId)
    return success(paginate(items, total, page, pageSize))


@router.get("/courses/teachers/search", summary="课程负责人检索（在职教师，供选择器）")
def course_teacher_search(keyword: Optional[str] = None, user=Depends(_COURSE_VIEW)):
    return success({"items": course_svc.search_teachers(keyword or "")})


@router.get("/courses/{courseId}", summary="课程详情")
def course_detail(courseId: int = Path(...), user=Depends(_COURSE_VIEW)):
    return success(course_svc.get_course(courseId, user))


@router.get("/courses/{courseId}/references", summary="课程引用情况（被哪些培养方案引用，供停用前提示）")
def course_references(courseId: int = Path(...), user=Depends(_COURSE_VIEW)):
    return success({"items": course_svc.get_course_references(courseId, user)})


# ── 课程材料 / 课程大纲（Tier1 R3：附件走 POST /api/v1/files/upload，本端点只登记回链）──

class CourseMaterialCreate(BaseModel):
    materialType: str = Field(..., description="SYLLABUS/COURSEWARE/LESSON_PLAN/EXERCISE/PRACTICE_GUIDE/OTHER")
    title: str = Field(..., min_length=1, max_length=200)
    fileId: Optional[str] = Field(None, description="先调 POST /api/v1/files/upload 得到的 fileId")
    fileName: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=500)


@router.get("/courses/{courseId}/materials", summary="课程材料/大纲列表（materialType=SYLLABUS 即课程大纲）")
def course_materials(courseId: int = Path(...), materialType: Optional[str] = None,
                     page: int = 1, pageSize: int = 50, user=Depends(_COURSE_VIEW)):
    items, total = course_svc.list_course_materials(courseId, user, materialType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/courses/{courseId}/materials", summary="新增课程材料/大纲")
def course_material_add(body: CourseMaterialCreate, courseId: int = Path(...), user=Depends(_COURSE_MANAGE)):
    return success(course_svc.add_course_material(courseId, user, body), message="已新增")


@router.delete("/courses/materials/{materialId}", summary="作废课程材料（逻辑删除）")
def course_material_void(materialId: int = Path(...), user=Depends(_COURSE_MANAGE)):
    return success(course_svc.void_course_material(materialId, user), message="已作废")


@router.put("/courses/{courseId}", summary="编辑课程（已启用改动强制新版本）")
def course_update(body: CourseCreate, courseId: int = Path(...), user=Depends(_COURSE_MANAGE)):
    return success(course_svc.update_course(courseId, user, body), message="已保存")


@router.post("/courses/{courseId}/submit", summary="提交课程审核")
def course_submit(courseId: int = Path(...), user=Depends(_COURSE_MANAGE)):
    return success(course_svc.submit_course(courseId, user), message="已提交")


@router.post("/courses/{courseId}/review", summary="课程两级审核（学院→教务→ENABLED）")
def course_review(body: AaReviewBody, courseId: int = Path(...), user=Depends(_COURSE_APPROVE)):
    return success(course_svc.review_course(courseId, user, body.action, body.reason or ""), message="已处理")


@router.post("/courses/{courseId}/enable", summary="启用课程（DISABLED→ENABLED）")
def course_enable(courseId: int = Path(...), user=Depends(_COURSE_APPROVE)):
    return success(course_svc.set_course_status(courseId, user, True), message="已启用")


@router.post("/courses/{courseId}/disable", summary="停用课程（ENABLED→DISABLED；被在途/生效培养方案引用时 400 拦截）")
def course_disable(courseId: int = Path(...), user=Depends(_COURSE_APPROVE)):
    return success(course_svc.set_course_status(courseId, user, False), message="已停用")


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


# ── 教学任务调整（管理员更正，续工新增）──

class AdjustTaskBody(BaseModel):
    teacherId: Optional[str] = None
    teacherKey: Optional[str] = None
    teacherName: Optional[str] = None
    weeklyHours: Optional[int] = None
    totalHours: Optional[int] = None
    startWeek: Optional[int] = None
    endWeek: Optional[int] = None
    expectedStudents: Optional[int] = None
    reason: str = Field(..., min_length=1, description="调整原因，必填且不少于 5 字（服务层校验）")


@router.post("/teaching-tasks/{taskId}/adjust", summary="教学任务调整（管理员更正教师/学时/周次/人数，理由必填+审计）")
def task_adjust(body: AdjustTaskBody, taskId: int = Path(...),
                user=Depends(require_permission("academicAffairs.teachingTask.adjust"))):
    return success(task_svc.adjust_task(taskId, user, body), message="已调整")


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


class ScheduleMoveBody(BaseModel):
    weekday: int = Field(..., ge=1, le=7)
    slotNo: int = Field(..., ge=1)


@router.put("/schedule-items/{itemId}/move", summary="拖拽调格（同一冲突检测器，冲突409原位不动）")
def schedule_move_item(body: ScheduleMoveBody, itemId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.move_item(itemId, user, body), message="已调整")


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


# ═══════════ 课表管理 Tier1 R2：班级/教师/教室独立课表 + 发布记录 + 导出（自动取当前已发布批次） ═══════════
_SCHED_TIER1_VIEW = "academicAffairs.schedule.view"  # 与 §2410 附近排课管理增强复用同一 key（module-wide 课表查看）
_SCHED_ROOM_VIEW = "academicAffairs.classroom.view"  # 复用既有教室字典权限点，不新增教室专属 key
_SCHED_EXPORT = "academicAffairs.schedule.export"


@router.get("/schedule/class/{classId}", summary="班级课表（自动取当前已发布批次；周次可选过滤；越范围403002）")
def schedule_class_page(classId: int = Path(...), termId: Optional[str] = None, week: Optional[int] = None,
                        user=Depends(require_permission(_SCHED_TIER1_VIEW))):
    return success(sched_svc.class_schedule(user, classId, termId, week))


@router.get("/schedule/teacher/{teacherKey}", summary="教师课表（教务处/学院教务查任意；教师仅本人，越权403002）")
def schedule_teacher_page(teacherKey: str = Path(...), termId: Optional[str] = None, week: Optional[int] = None,
                          user=Depends(require_permission(_SCHED_TIER1_VIEW))):
    return success(sched_svc.teacher_schedule(user, teacherKey, termId, week))


@router.get("/schedule/room/{classroomId}", summary="教室课表（教务/学院教务只读；自动取当前已发布批次）")
def schedule_room_page(classroomId: int = Path(...), termId: Optional[str] = None, week: Optional[int] = None,
                       user=Depends(require_permission(_SCHED_ROOM_VIEW))):
    return success(sched_svc.room_schedule(user, classroomId, termId, week))


@router.get("/schedule/student/{studentId}", summary="学生课表（按行政班+本人LOCKED选课并入；自动取当前已发布批次；越范围403002）")
def schedule_student_page(studentId: int = Path(...), termId: Optional[str] = None, week: Optional[int] = None,
                          user=Depends(require_permission(_SCHED_TIER1_VIEW))):
    return success(sched_svc.student_schedule(user, studentId, termId, week))


@router.get("/schedule/teaching-class/{teachingClassCode}", summary="教学班课表（派生自教学任务；自动取当前已发布批次；越范围403002）")
def schedule_teaching_class_page(teachingClassCode: str = Path(...), termId: Optional[str] = None,
                                 week: Optional[int] = None, user=Depends(require_permission(_SCHED_TIER1_VIEW))):
    return success(sched_svc.teaching_class_schedule(user, teachingClassCode, termId, week))


@router.get("/schedule/publish-records", summary="课表发布记录（t_aa_schedule_publish，发布/作废历史留痕）")
def schedule_publish_records(termId: Optional[str] = None, batchId: Optional[str] = None,
                             page: int = 1, pageSize: int = 20, user=Depends(require_permission(_SCHED_TIER1_VIEW))):
    items, total = sched_svc.list_publish_records(user, termId, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/schedule/adjustments", summary="课表调整记录（读 t_affairs_audit_trail：条目/批次两级变更留痕，只读）")
def schedule_adjustments(bizType: Optional[str] = None, action: Optional[str] = None,
                         page: int = 1, pageSize: int = 20, user=Depends(require_permission(_SCHED_TIER1_VIEW))):
    items, total = sched_svc.list_schedule_adjustments(user, bizType, action, page, pageSize)
    return success(paginate(items, total, page, pageSize))


class ScheduleExportBody(BaseModel):
    scope: str = Field(..., description="CLASS/TEACHER/ROOM")
    identifier: str = Field(..., min_length=1, description="classId / teacherKey / classroomId")
    termId: Optional[str] = None
    weekStart: Optional[int] = Field(None, ge=1)
    weekEnd: Optional[int] = Field(None, ge=1)
    purpose: str = Field(..., min_length=5, description="导出用途（≥5字，写审计）")


@router.post("/schedule/export", summary="课表导出 xlsx（班级/教师/教室三选一；水印+审计）")
def schedule_export(body: ScheduleExportBody, user=Depends(require_permission(_SCHED_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content = sched_svc.export_schedule(user, body.scope, body.identifier, body.termId,
                                        body.weekStart, body.weekEnd, body.purpose)
    return StreamingResponse(io.BytesIO(content),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=schedule_export.xlsx"})


# ═══════════ 成绩录入 + 读侧视图（P5，平时+期末按比例）═══════════

class GradeTaskCreate(BaseModel):
    teachingTaskId: Optional[str] = None
    termId: Optional[str] = None
    termCode: Optional[str] = None
    courseName: str = Field(..., min_length=1)
    classId: Optional[str] = None
    credit: Optional[float] = None
    usualRatio: int = Field(30, ge=0, le=100, description="平时占比%")
    midtermRatio: int = Field(0, ge=0, le=100, description="期中占比%(0=不启用期中)")
    finalRatio: int = Field(70, ge=0, le=100, description="期末占比%")
    passLine: int = Field(60, ge=0, le=100)


class ScoreBody(BaseModel):
    studentId: str = Field(..., min_length=1)
    usualScore: Optional[int] = Field(None, ge=0, le=100)
    midtermScore: Optional[int] = Field(None, ge=0, le=100)
    finalScore: Optional[int] = Field(None, ge=0, le=100)
    exceptionFlag: Optional[str] = Field(None, description="NORMAL/ABSENT/DEFERRED/EXEMPT")


class GradeImportRowsBody(BaseModel):
    rows: List[dict] = Field(default_factory=list)


class GradeImportErrorsBody(BaseModel):
    rows: List[dict] = Field(default_factory=list)
    errors: List[dict] = Field(default_factory=list)


class TranscriptExportBody(BaseModel):
    purpose: str = Field(..., min_length=5, description="导出用途（≥5 字，必填，写审计）")


class GradeReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/RETURN")
    reason: Optional[str] = Field("", max_length=500)


class GradeReturnBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class GradeChangeRequestBody(BaseModel):
    newUsualScore: Optional[int] = Field(None, ge=0, le=100)
    newMidtermScore: Optional[int] = Field(None, ge=0, le=100)
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


@router.get("/grade-tasks/{taskId}/records", summary="成绩录入表当前已录状态（供刷新/批量导入后回显）")
def grade_records(taskId: int = Path(...), user=Depends(require_permission("academicAffairs.grade.input"))):
    return success(grade_svc.list_records(taskId, user))


@router.post("/grade-tasks/{taskId}/scores", summary="录入平时/期末分（实时合成总评）")
def grade_enter_score(body: ScoreBody, taskId: int = Path(...),
                      user=Depends(require_permission("academicAffairs.grade.input"))):
    return success(grade_svc.enter_score(taskId, user, body), message="已录入")


# ── 成绩批量导入（学号/平时分/期末分/异常标记；dry-run 行级错误 → 确认整批事务） ──
@router.get("/grade-tasks/{taskId}/import/template", summary="成绩批量导入·下载 Excel 模板(.xlsx)")
def grade_import_template(taskId: int = Path(...), user=Depends(require_permission("academicAffairs.grade.input"))):
    import io

    from fastapi.responses import StreamingResponse
    from app.services import xlsx_util
    data = xlsx_util.build_template_xlsx(grade_svc.IMPORT_HEADERS, sample=grade_svc.IMPORT_SAMPLE,
                                         notes=grade_svc.IMPORT_NOTES, required=grade_svc.IMPORT_REQUIRED)
    return StreamingResponse(io.BytesIO(data),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=grade_import_template.xlsx"})


@router.post("/grade-tasks/{taskId}/import/xlsx", summary="上传 Excel(.xlsx)·解析并预校验（不写库）")
async def grade_import_xlsx(taskId: int = Path(...), file: UploadFile = File(...),
                            user=Depends(require_permission("academicAffairs.grade.input"))):
    from app.services import xlsx_util
    content = await file.read()
    rows = xlsx_util.read_xlsx(content, grade_svc.IMPORT_HEADER_MAP)
    return success({**grade_svc.grade_import_dry_run(taskId, user, rows), "rows": rows})


@router.post("/grade-tasks/{taskId}/import/errors-xlsx", summary="下载错误行 Excel(.xlsx)")
def grade_import_errors_xlsx(body: GradeImportErrorsBody, taskId: int = Path(...),
                             user=Depends(require_permission("academicAffairs.grade.input"))):
    import io

    from fastapi.responses import StreamingResponse
    from app.services import xlsx_util
    data = xlsx_util.build_error_rows_xlsx(grade_svc.IMPORT_HEADERS, body.rows, body.errors,
                                           grade_svc._row_values_for_error)
    return StreamingResponse(io.BytesIO(data),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=grade_import_errors.xlsx"})


@router.post("/grade-tasks/{taskId}/import/confirm", summary="成绩批量导入·确认（整批事务，逐行落 t_aa_grade_record）")
def grade_import_confirm(body: GradeImportRowsBody, taskId: int = Path(...),
                         user=Depends(require_permission("academicAffairs.grade.input"))):
    result = grade_svc.grade_import_confirm(taskId, user, body.rows)
    return success(result, message="导入完成")


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


# ── 成绩认定/课程替代（转专业/转学：原修课程替代现计划课程，审核通过写 source=RECOGNIZED）──
class RecognitionSubmitBody(BaseModel):
    sourceCourseName: str = Field(..., min_length=1, max_length=200)
    sourceScore: int = Field(..., ge=0, le=100)
    sourceCredit: Optional[float] = Field(None, ge=0, le=30)
    sourceOrigin: Optional[str] = Field(None, max_length=300)
    targetCourseId: Optional[str] = Field(None, description="课程库选择器；优先于 targetCourseName")
    targetCourseName: Optional[str] = Field(None, max_length=200, description="手填目标课程（无选择器时）")
    attachmentFileIds: Optional[list[str]] = Field(None, description="佐证附件 file_id 列表")
    reason: Optional[str] = Field(None, max_length=500)
    studentNo: Optional[str] = Field(None, description="教务代录时必填；学生自助忽略")


class RecognitionReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    reason: Optional[str] = Field("", max_length=500)


@router.post("/grade-recognitions", summary="教务代录成绩认定申请")
def recog_submit_staff(body: RecognitionSubmitBody,
                       user=Depends(require_permission("academicAffairs.gradeRecognition.manage"))):
    if not body.studentNo:
        raise AppException("VALIDATION_ERROR", "教务代录必须提供学号")
    return success(recog_svc.submit(user, body, student_no=body.studentNo), message="已提交认定申请")


@router.get("/grade-recognitions", summary="成绩认定列表")
def recog_list(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
               user=Depends(require_permission("academicAffairs.gradeRecognition.view"))):
    items, total = recog_svc.list_all(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/grade-recognitions/{rid}/review", summary="教务审核（通过写 RECOGNIZED 成绩并刷新台账）")
def recog_review(body: RecognitionReviewBody, rid: int = Path(...),
                 user=Depends(require_permission("academicAffairs.gradeRecognition.manage"))):
    return success(recog_svc.review(user, rid, body.action, body.reason or ""), message="已处理")


@router.post("/grade-recognitions/student/submit", summary="学生自助提交认定申请")
def recog_submit_student(body: RecognitionSubmitBody, user=Depends(_require_student)):
    return success(recog_svc.submit(user, body), message="已提交认定申请")


@router.get("/grade-recognitions/my", summary="我的认定申请")
def recog_my(user=Depends(_require_student)):
    return success({"items": recog_svc.my(user)})


@router.get("/students/{studentId}/transcript", summary="学生成绩单（读侧）")
def grade_transcript(studentId: int = Path(...), user=Depends(require_permission("academicAffairs.grade.view"))):
    return success(grade_svc.transcript(studentId, user))


@router.post("/students/{studentId}/transcript/export", summary="导出学生成绩单 xlsx（水印+审计+用途必填，同步下载）")
def grade_transcript_export(body: TranscriptExportBody, studentId: int = Path(...),
                            user=Depends(require_permission("academicAffairs.grade.export"))):
    import io

    from fastapi.responses import StreamingResponse
    content = grade_svc.export_transcript_xlsx(user, studentId, body.purpose)
    return StreamingResponse(io.BytesIO(content),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=student_transcript.xlsx"})


@router.get("/grade-views/fail-list", summary="挂科清单（读侧下钻）")
def grade_fail_list(term: Optional[str] = None, page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = grade_svc.fail_list(user, term, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/grade-views/analysis", summary="成绩分析（分数段+及格率+优秀率+平均分，可按课程/班级分组）")
def grade_analysis(term: Optional[str] = None, dimension: Optional[str] = None,
                   user=Depends(require_staff)):
    return success(grade_svc.grade_analysis(user, term, dimension))


class GradeAnalysisExportBody(BaseModel):
    term: Optional[str] = None
    dimension: str = "course"
    purpose: str = Field(..., min_length=5, description="导出用途（≥5 字，写审计）")


@router.post("/grade-views/analysis/export", summary="成绩分析统计表导出 xlsx（按课程/班级，水印+审计，同步下载）")
def grade_analysis_export(body: GradeAnalysisExportBody,
                          user=Depends(require_permission("academicAffairs.grade.view"))):
    import io

    from fastapi.responses import StreamingResponse
    content = grade_svc.export_grade_analysis_xlsx(user, body.term, body.dimension, body.purpose)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=grade_analysis.xlsx"})


# ═══════════ 课堂考勤（PC 只读查询/统计；教师逐生录入在移动端，正方 教学点名 2.4/查询 4.19 对标）═══════════
@router.get("/attendance/sessions", summary="课堂考勤场次列表（PC 查询，按行政班/学期/类别筛选，数据范围收敛）")
def attendance_sessions_list(classId: Optional[str] = None, termCode: Optional[str] = None,
                             sessionType: Optional[str] = None, page: int = 1, pageSize: int = 20,
                             user=Depends(require_staff)):
    items, total = attendance_svc.list_sessions(user, page, pageSize, classId, termCode, sessionType)
    return success(paginate(items, total, page, pageSize))


@router.get("/attendance/sessions/{sessionId}", summary="课堂考勤场次详情+名单")
def attendance_session_detail(sessionId: int = Path(...), user=Depends(require_staff)):
    return success(attendance_svc.get_session(sessionId, user))


@router.get("/attendance/stats", summary="跨堂次考勤统计（按学生汇总出勤/迟到/旷课/请假+缺勤率，正方4.19对标）")
def attendance_stats_view(classId: Optional[str] = None, termCode: Optional[str] = None,
                          sessionType: Optional[str] = None, user=Depends(require_staff)):
    return success(attendance_svc.attendance_stats(user, classId, termCode, sessionType))


# ═══════════ 成绩复查（学生发起在移动端；教务处复审在 PC，正方 学生端3.12/教师端3.11 对标）═══════════
@router.get("/grade-rechecks", summary="成绩复查台账（教务处，按状态筛选）")
def grade_recheck_list(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                       user=Depends(require_permission("academicAffairs.grade.view"))):
    items, total = recheck_svc.list_all(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


class GradeRecheckReviewBody(BaseModel):
    action: str = Field(..., description="UPHOLD 维持 / ADJUST 调整 / REJECT 不予受理")
    note: Optional[str] = Field("", max_length=500)
    newScore: Optional[int] = Field(None, ge=0, le=100, description="ADJUST 时必填")


@router.post("/grade-rechecks/{recheckId}/review", summary="成绩复查复审（维持/调整回写t_acad_grade+通知学生/不予受理）")
def grade_recheck_review(body: GradeRecheckReviewBody, recheckId: int = Path(...),
                         user=Depends(require_permission("academicAffairs.grade.publish"))):
    return success(recheck_svc.review(user, recheckId, body.action, body.note, body.newScore))


# ═══════════ 教师工作量申报（教师端申报在移动端；教务处审核在 PC，正方教师端1.18/1.19对标）═══════════
@router.get("/workload-declarations", summary="工作量申报台账（教务处，按状态/学期筛选）")
def workload_decl_list(status: Optional[str] = None, termCode: Optional[str] = None,
                       page: int = 1, pageSize: int = 20,
                       user=Depends(require_permission("academicAffairs.stats.view"))):
    items, total = workload_svc.list_all(user, status, termCode, page, pageSize)
    return success(paginate(items, total, page, pageSize))


class WorkloadReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE 通过 / REJECT 驳回")
    note: Optional[str] = Field("", max_length=500)


@router.post("/workload-declarations/{declId}/review", summary="工作量申报审核（通过计入统计/驳回）")
def workload_decl_review(body: WorkloadReviewBody, declId: int = Path(...),
                         user=Depends(require_permission("academicAffairs.stats.view"))):
    return success(workload_svc.review(user, declId, body.action, body.note))


@router.get("/grade-views/exception-list", summary="成绩异常清单（缺考/缓考/免修标记学生汇总，读侧下钻）")
def grade_exception_list(term: Optional[str] = None, exceptionFlag: Optional[str] = None,
                         page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = grade_svc.exception_list(user, term, exceptionFlag, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/grade-views/audit", summary="成绩操作审计（读侧，AA_GRADE_*；教务处/学院查全量，教师自查本人）")
def grade_audit_list(bizType: Optional[str] = None, page: int = 1, pageSize: int = 50,
                     user=Depends(require_permission("academicAffairs.grade.view"))):
    items, total = grade_svc.list_grade_audit(user, bizType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


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


# 注意：静态子路径必须注册在 /warnings/{warningId} 之前（同 /warnings/rules、/warnings/summary），
# 否则 Starlette 会把 "notifications" 当作 warningId 匹配到 /warnings/{warningId}，因 int 校验失败 422。
@router.get("/warnings/notifications", summary="预警通知台账（已推送的站内通知列表）")
def warning_notifications(warningId: Optional[int] = None, page: int = 1, pageSize: int = 20,
                          user=Depends(require_permission(_WARN_VIEW))):
    items, total = warn_svc.list_notifications(user, warningId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/warnings/notifications/summary", summary="预警通知台账统计（累计/未读/已读）")
def warning_notifications_summary(user=Depends(require_permission(_WARN_VIEW))):
    return success(warn_svc.notification_summary(user))


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


# ── 毕业/结业证书管理（编号规则+批量生成+台账+发放+作废）──
class CertGenerateBody(BaseModel):
    prefix: str = Field(..., min_length=1, max_length=20, description="编号前缀(学校代码)")
    year: str = Field(..., min_length=4, max_length=4, description="签发年份")
    eRegPrefix: Optional[str] = Field(None, max_length=20, description="电子注册号前缀(空=不生成)")
    issueDate: Optional[str] = Field(None, description="签发日期 YYYY-MM-DD")


class CertVoidBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


@router.post("/graduation-batches/{batchId}/certificates/generate",
             summary="按终审结论批量生成证书编号（毕业证/结业证，幂等跳过已有）")
def cert_generate(body: CertGenerateBody, batchId: int = Path(...),
                  user=Depends(require_permission("academicAffairs.graduationCert.manage"))):
    r = grad_svc.generate_certificates(batchId, user, body)
    return success(r, message=f"已生成 {r['created']} 张（跳过已有 {r['skipped']}）")


@router.get("/graduation-certificates", summary="证书台账")
def cert_list(status: Optional[str] = None, certType: Optional[str] = None,
              batchId: Optional[str] = None, keyword: Optional[str] = None,
              page: int = 1, pageSize: int = 50,
              user=Depends(require_permission("academicAffairs.graduationCert.view"))):
    items, total = grad_svc.list_certificates(user, status, certType, batchId, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/graduation-certificates/{certId}/issue", summary="登记发放（GENERATED→ISSUED）")
def cert_issue(certId: int = Path(...),
               user=Depends(require_permission("academicAffairs.graduationCert.manage"))):
    return success(grad_svc.issue_certificate(certId, user), message="已登记发放")


@router.post("/graduation-certificates/{certId}/void", summary="作废（原因≥5字；编号不回收）")
def cert_void(body: CertVoidBody, certId: int = Path(...),
              user=Depends(require_permission("academicAffairs.graduationCert.manage"))):
    return success(grad_svc.void_certificate(certId, user, body.reason), message="已作废")


# ══════════════ 教务统计（只读聚合，/academic-affairs/stats/*） ══════════════
# 全部端点挂 require_permission("academicAffairs.stats.*")（通配 academicAffairs.* 覆盖教务处/学院/教师；
# LEADER 命中 *.view）；数据范围复用 build_affairs_context（详见 stats_service）。学生令牌 STAFF/STUDENT 无授权 → 403。
_STATS_VIEW = "academicAffairs.stats.view"
_STATS_EXPORT = "academicAffairs.stats.export"


@router.get("/stats/overview", summary="教务统计总览（15 项指标，2026-07-16 起全部真实聚合）")
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


# ── 教务统计第三轮续工（2026-07-16）：08/09/14 号卡（选课/考务/教学资源统计，跨批次聚合，全新路径）。
#    07 调停课统计不在本节：其完整交互见独立页面 /schedule-change/stats（已存在，权限
#    academicAffairs.scheduleChange.view），本节 overview() 已提供全局计数卡（见 stats_svc 模块头注释）。
@router.get("/stats/course-selection", summary="选课统计聚合（跨批次容量/已选/填充率，08 号卡）")
def stats_course_selection(termId: Optional[int] = None, collegeId: Optional[int] = None,
                           user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.course_selection_stats(user, termId, collegeId))


@router.get("/stats/course-selection/detail", summary="选课统计下钻：低人数课程清单（08 号卡）")
def stats_course_selection_detail(termId: Optional[int] = None, collegeId: Optional[int] = None,
                                  page: int = 1, pageSize: int = 20,
                                  user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.course_selection_detail(user, termId, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/exam", summary="考务统计聚合（跨批次课程确认率+缺考/违纪，09 号卡）")
def stats_exam(termId: Optional[int] = None, collegeId: Optional[int] = None,
               user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.exam_stats(user, termId, collegeId))


@router.get("/stats/exam/detail", summary="考务统计下钻：缺考/违纪明细（脱敏+审计，09 号卡）")
def stats_exam_detail(termId: Optional[int] = None, collegeId: Optional[int] = None,
                      incidentType: Optional[str] = None, page: int = 1, pageSize: int = 20,
                      user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.exam_detail(user, termId, collegeId, incidentType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/resource", summary="教学资源统计聚合（教室状态/类型+预约状态分布，14 号卡）")
def stats_resource(user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.resource_stats(user))


@router.get("/stats/resource/detail", summary="教学资源统计下钻：待审核教室预约清单（14 号卡）")
def stats_resource_detail(page: int = 1, pageSize: int = 20,
                          user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.resource_detail(user, page, pageSize)
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


class MajorDirectionToggleBody(BaseModel):
    enabled: bool = False


class DirectionBody(BaseModel):
    directionName: Optional[str] = None
    code: Optional[str] = None


class ClassAdjustmentCreateBody(BaseModel):
    adjustType: str = Field(..., min_length=1)
    fromClassIds: List[str] = Field(default_factory=list)
    toClassId: Optional[str] = None
    reason: str = Field(..., min_length=1)


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


@router.get("/orgs/classes/{classId}/students", summary="班级学生列表（07号卡：性别/学籍状态/手机号脱敏+关键字）")
def org_class_students(classId: int = Path(...), keyword: Optional[str] = None,
                       page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_class_students(user, classId, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/orgs/class-adjustments", summary="班级调整（移动单个学生，单写入口+审计）")
def org_class_adjust(body: ClassAdjustBody, user=Depends(_ORG_MANAGE)):
    return success(org_svc.adjust_student_class(user, body), message="已调整")


# ── 专业方向（06号卡：总开关默认关闭，业务政策待学校确认；启用后学院教务在专业下维护方向）──
@router.get("/orgs/major-direction-toggle", summary="专业方向总开关状态")
def org_direction_toggle_get(user=Depends(_ORG_VIEW)):
    return success(org_svc.get_major_direction_toggle(user))


@router.post("/orgs/major-direction-toggle", summary="设置专业方向总开关（仅教务处/校管）")
def org_direction_toggle_set(body: MajorDirectionToggleBody, user=Depends(_ORG_MANAGE)):
    return success(org_svc.set_major_direction_toggle(user, body.enabled), message="已保存")


@router.get("/orgs/majors/{majorId}/directions", summary="专业方向列表")
def org_directions(majorId: int = Path(...), page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_directions(user, majorId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/orgs/majors/{majorId}/directions", summary="新建专业方向")
def org_direction_create(body: DirectionBody, majorId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.create_direction(user, majorId, body), message="已创建")


@router.put("/orgs/majors/{majorId}/directions/{directionId}", summary="编辑专业方向")
def org_direction_update(body: DirectionBody, majorId: int = Path(...), directionId: int = Path(...),
                         user=Depends(_ORG_MANAGE)):
    return success(org_svc.update_direction(user, majorId, directionId, body), message="已保存")


@router.post("/orgs/majors/{majorId}/directions/{directionId}/disable", summary="停用专业方向")
def org_direction_disable(majorId: int = Path(...), directionId: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.disable_direction(user, majorId, directionId), message="已停用")


# ── 班级调整申请单（08号卡：行政班层面批量组织调整——合班/拆班/停用/毕业清班，区别于上方个体学生转班）──
@router.get("/orgs/class-adjustment-requests", summary="班级调整申请单列表")
def org_adjustment_list(status: Optional[str] = None, adjustType: Optional[str] = None,
                        page: int = 1, pageSize: int = 50, user=Depends(_ORG_VIEW)):
    items, total = org_svc.list_class_adjustments(user, status, adjustType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/orgs/class-adjustment-requests", summary="发起班级调整申请")
def org_adjustment_create(body: ClassAdjustmentCreateBody, user=Depends(_ORG_MANAGE)):
    return success(org_svc.create_class_adjustment(user, body), message="已发起")


@router.post("/orgs/class-adjustment-requests/{id}/precheck", summary="前置核对")
def org_adjustment_precheck(id: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.precheck_class_adjustment(user, id))


@router.post("/orgs/class-adjustment-requests/{id}/execute", summary="确认执行")
def org_adjustment_execute(id: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.execute_class_adjustment(user, id), message="已执行")


@router.post("/orgs/class-adjustment-requests/{id}/cancel", summary="撤销")
def org_adjustment_cancel(id: int = Path(...), user=Depends(_ORG_MANAGE)):
    return success(org_svc.cancel_class_adjustment(user, id), message="已撤销")


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


# 注：classroom_detail 的 {classroomId} 必须注册在上面字面量路径 /classrooms/bookings 之后——
# FastAPI 按声明顺序匹配路由，{classroomId} 若先声明会把 "bookings" 当成 classroomId 抢先匹配，
# 导致教室预约列表端点被遮蔽（本条是总控合并复核用全量扫描脚本发现并修复的真实路由顺序 bug，
# 已存在于此前 Round1 版本、非本轮引入，此次一并修正）。
@router.get("/classrooms/{classroomId}", summary="教室详情")
def classroom_detail(classroomId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.classroom.view"))):
    return success(resource_svc.get_classroom(classroomId, user))


@router.post("/classrooms/bookings/{bookingId}/review", summary="审核教室预约")
def classroom_booking_review(body: BookingReviewBody, bookingId: int = Path(...),
                             user=Depends(require_permission("academicAffairs.classroom.update"))):
    return success(resource_svc.review_booking(user, bookingId, body.action, body.reason), message="已处理")


# ═══════════ 教学资源续卡：实训室资源 / 设备资源 / 实训室预约 / 资源占用 / 资源冲突 / 资源维修 / 资源统计
# （教室字典框架扩展；权限点延续既有 academicAffairs.classroom.* 风格） ═══════════


class LabCreate(BaseModel):
    labCode: str = Field(..., min_length=1, description="实训室编号")
    labName: str = Field(..., min_length=1, description="实训室名称")
    buildingName: Optional[str] = None
    capacity: Optional[int] = Field(0, ge=0, description="容量(工位数)")
    labType: Optional[str] = Field("SKILL", description="SKILL/COMPUTER/MECHANICAL/ELECTRICAL/OTHER")
    responsibleName: Optional[str] = None
    responsibleKey: Optional[str] = None
    remark: Optional[str] = None


class LabUpdate(BaseModel):
    labCode: Optional[str] = None
    labName: Optional[str] = None
    buildingName: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)
    labType: Optional[str] = None
    responsibleName: Optional[str] = None
    responsibleKey: Optional[str] = None
    remark: Optional[str] = None


class LabStatusBody(BaseModel):
    status: str = Field(..., description="AVAILABLE/DISABLED/MAINTENANCE")
    reason: Optional[str] = None


@router.get("/labs", summary="实训室字典列表（按类型/状态/关键词过滤）")
def lab_list(keyword: Optional[str] = None, labType: Optional[str] = None, status: Optional[str] = None,
            page: int = 1, pageSize: int = 20, user=Depends(require_permission("academicAffairs.lab.view"))):
    items, total = resource_svc.list_labs(user, keyword, labType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/labs/options", summary="可用实训室选项（预约选择器供数）")
def lab_options(keyword: Optional[str] = None, user=Depends(require_permission("academicAffairs.lab.view"))):
    return success({"items": resource_svc.list_lab_options(user, keyword)})


@router.post("/labs", summary="新建实训室（编号唯一，重复409）")
def lab_create(body: LabCreate, user=Depends(require_permission("academicAffairs.lab.create"))):
    return success(resource_svc.create_lab(body, user), message="已创建")


@router.put("/labs/{labId}", summary="编辑实训室")
def lab_update(body: LabUpdate, labId: int = Path(...),
               user=Depends(require_permission("academicAffairs.lab.update"))):
    return success(resource_svc.update_lab(labId, body, user), message="已保存")


@router.post("/labs/{labId}/status", summary="切换可用状态（AVAILABLE/DISABLED/MAINTENANCE，幂等）")
def lab_status(body: LabStatusBody, labId: int = Path(...),
               user=Depends(require_permission("academicAffairs.lab.update"))):
    return success(resource_svc.set_lab_status(labId, body.status, user, body.reason or ""), message="已更新")


@router.delete("/labs/{labId}", summary="删除实训室（逻辑删除）")
def lab_delete(labId: int = Path(...), user=Depends(require_permission("academicAffairs.lab.delete"))):
    return success(resource_svc.delete_lab(labId, user), message="已删除")


# ── 实训室预约（占用登记+冲突检测+审核；字面量路径须注册在 /labs/{labId} 之前，同教室预约既有教训） ──
class LabBookBody(BaseModel):
    labId: str = Field(..., min_length=1)
    bookingDate: str = Field(..., min_length=1, description="YYYY-MM-DD")
    slotNo: int = Field(..., ge=1)
    purpose: Optional[str] = Field(None, max_length=300)


@router.post("/labs/bookings", summary="申请实训室预约（同实训室同时段占用409）")
def lab_book(body: LabBookBody, user=Depends(require_staff)):
    return success(resource_svc.book_lab(user, body), message="已提交预约")


@router.get("/labs/bookings", summary="实训室预约列表")
def lab_bookings(labId: Optional[str] = None, date: Optional[str] = None, status: Optional[str] = None,
                 page: int = 1, pageSize: int = 50,
                 user=Depends(require_permission("academicAffairs.lab.view"))):
    items, total = resource_svc.list_lab_bookings(user, labId, date, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/labs/bookings/{bookingId}/review", summary="审核实训室预约")
def lab_booking_review(body: BookingReviewBody, bookingId: int = Path(...),
                       user=Depends(require_permission("academicAffairs.lab.update"))):
    return success(resource_svc.review_lab_booking(user, bookingId, body.action, body.reason), message="已处理")


@router.get("/labs/{labId}", summary="实训室详情")
def lab_detail(labId: int = Path(...), user=Depends(require_permission("academicAffairs.lab.view"))):
    return success(resource_svc.get_lab(labId, user))


# ── 设备资源（教学/实训设备台账） ──
class EquipmentCreate(BaseModel):
    equipmentCode: str = Field(..., min_length=1, description="资产编号")
    equipmentName: str = Field(..., min_length=1, description="设备名称")
    specModel: Optional[str] = None
    quantity: Optional[int] = Field(1, ge=1)
    ownerKind: Optional[str] = Field("NONE", description="CLASSROOM/LAB/NONE")
    ownerId: Optional[str] = None
    responsibleName: Optional[str] = None
    purchaseDate: Optional[str] = None
    status: Optional[str] = Field("IN_USE", description="IN_USE/IDLE/MAINTENANCE/SCRAPPED")
    remark: Optional[str] = None


class EquipmentUpdate(BaseModel):
    equipmentCode: Optional[str] = None
    equipmentName: Optional[str] = None
    specModel: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1)
    ownerKind: Optional[str] = None
    ownerId: Optional[str] = None
    responsibleName: Optional[str] = None
    purchaseDate: Optional[str] = None
    remark: Optional[str] = None


class EquipmentStatusBody(BaseModel):
    status: str = Field(..., description="IN_USE/IDLE/MAINTENANCE/SCRAPPED")
    reason: Optional[str] = None


@router.get("/equipment", summary="设备资源列表（按位置/状态/关键词过滤）")
def equipment_list(keyword: Optional[str] = None, ownerKind: Optional[str] = None, status: Optional[str] = None,
                   page: int = 1, pageSize: int = 20,
                   user=Depends(require_permission("academicAffairs.equipment.view"))):
    items, total = resource_svc.list_equipment(user, keyword, ownerKind, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/equipment", summary="新建设备（资产编号唯一，重复409）")
def equipment_create(body: EquipmentCreate, user=Depends(require_permission("academicAffairs.equipment.create"))):
    return success(resource_svc.create_equipment(body, user), message="已创建")


@router.put("/equipment/{equipmentId}", summary="编辑设备")
def equipment_update(body: EquipmentUpdate, equipmentId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.equipment.update"))):
    return success(resource_svc.update_equipment(equipmentId, body, user), message="已保存")


@router.post("/equipment/{equipmentId}/status", summary="切换设备状态（IN_USE/IDLE/MAINTENANCE/SCRAPPED，幂等）")
def equipment_status(body: EquipmentStatusBody, equipmentId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.equipment.update"))):
    return success(resource_svc.set_equipment_status(equipmentId, body.status, user, body.reason or ""),
                   message="已更新")


@router.delete("/equipment/{equipmentId}", summary="删除设备（逻辑删除）")
def equipment_delete(equipmentId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.equipment.delete"))):
    return success(resource_svc.delete_equipment(equipmentId, user), message="已删除")


@router.get("/equipment/{equipmentId}", summary="设备详情")
def equipment_detail(equipmentId: int = Path(...),
                     user=Depends(require_permission("academicAffairs.equipment.view"))):
    return success(resource_svc.get_equipment(equipmentId, user))


# ── 资源占用（教室+实训室已批准预约 + 当日课表，统一只读聚合视图） ──
@router.get("/resources/occupancy", summary="资源占用（教室+实训室已批准预约+当日课表，统一只读视图）")
def resource_occupancy(date: str, resourceKind: Optional[str] = None,
                       user=Depends(require_permission("academicAffairs.resourceOccupancy.view"))):
    return success(resource_svc.get_resource_occupancy(user, date, resourceKind))


# ── 资源冲突（预约 vs 已发布课表跨源冲突台账，区别于排课模块批次内冲突检测） ──
@router.get("/resources/conflicts", summary="资源冲突台账（预约 vs 已发布课表跨源冲突，日期范围最多31天）")
def resource_conflicts(dateFrom: str, dateTo: Optional[str] = None,
                       user=Depends(require_permission("academicAffairs.resourceConflict.view"))):
    return success(resource_svc.list_resource_conflicts(user, dateFrom, dateTo))


# ── 资源维修（教室/实训室/设备共用工单台账；报修→维修中→完成，联动资源状态） ──
class RepairReportBody(BaseModel):
    resourceKind: str = Field(..., description="CLASSROOM/LAB/EQUIPMENT")
    resourceId: str = Field(..., min_length=1)
    faultDesc: str = Field(..., min_length=1, max_length=500)


class RepairCompleteBody(BaseModel):
    repairNote: Optional[str] = Field("", max_length=500)


class RepairCancelBody(BaseModel):
    reason: Optional[str] = Field("", max_length=300)


@router.post("/resources/repairs", summary="登记故障报修（联动资源状态置为维修中）")
def repair_report(body: RepairReportBody, user=Depends(require_staff)):
    return success(resource_svc.report_repair(user, body), message="已登记报修")


@router.get("/resources/repairs", summary="维修工单列表")
def repair_list(resourceKind: Optional[str] = None, status: Optional[str] = None,
                page: int = 1, pageSize: int = 50,
                user=Depends(require_permission("academicAffairs.resourceRepair.view"))):
    items, total = resource_svc.list_repairs(user, resourceKind, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/resources/repairs/{repairId}/start", summary="开始维修")
def repair_start(repairId: int = Path(...),
                 user=Depends(require_permission("academicAffairs.resourceRepair.manage"))):
    return success(resource_svc.start_repair(user, repairId), message="已开始维修")


@router.post("/resources/repairs/{repairId}/complete", summary="完成维修（联动恢复资源可用，若无其它未完成工单）")
def repair_complete(body: RepairCompleteBody, repairId: int = Path(...),
                    user=Depends(require_permission("academicAffairs.resourceRepair.manage"))):
    return success(resource_svc.complete_repair(user, repairId, body.repairNote or ""), message="已完成")


@router.post("/resources/repairs/{repairId}/cancel", summary="取消维修工单")
def repair_cancel(body: RepairCancelBody, repairId: int = Path(...),
                  user=Depends(require_permission("academicAffairs.resourceRepair.manage"))):
    return success(resource_svc.cancel_repair(user, repairId, body.reason or ""), message="已取消")


# ── 资源统计（数量/状态分布/预约审批率/维修工单，只读聚合） ──
@router.get("/resources/stats", summary="资源统计（数量/状态分布/预约审批率/维修工单，只读聚合）")
def resource_stats(user=Depends(require_permission("academicAffairs.resourceStats.view"))):
    return success(resource_svc.get_resource_stats(user))


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


class ScheduleChangeConflictCheckBody(BaseModel):
    originItemId: str = Field(..., min_length=1, description="原课表项 id（须为已发布课表本人课位）")
    targetWeekday: int = Field(..., ge=1, le=7, description="目标星期")
    targetSlotNo: int = Field(..., ge=1, description="目标节次")
    targetStartWeek: Optional[int] = Field(None, ge=1)
    targetEndWeek: Optional[int] = Field(None, ge=1)
    targetWeekParity: Optional[str] = Field(None, description="ALL/ODD/EVEN")
    targetClassroom: Optional[str] = None


@router.post("/schedule-change", summary="发起调停课（提交即目标冲突预检；冲突单据不落库）")
def schedule_change_submit(body: ScheduleChangeSubmit,
                           user=Depends(require_permission("academicAffairs.scheduleChange.apply"))):
    return success(sched_change_svc.submit(body, user), message="调停课已提交")


@router.get("/schedule-change", summary="调停课台账（范围过滤）")
def schedule_change_list(changeType: Optional[str] = None, status: Optional[str] = None,
                         teacherKey: Optional[str] = None, termId: Optional[str] = None,
                         page: int = 1, pageSize: int = 20,
                         user=Depends(require_permission("academicAffairs.scheduleChange.view"))):
    items, total = sched_change_svc.list_changes(user, change_type=changeType, status=status,
                                                 teacher_key=teacherKey, term_id=termId,
                                                 page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/schedule-change/stats", summary="调停课统计（按类型/状态/学院/教师聚合）")
def schedule_change_stats(termId: Optional[str] = None, dimension: Optional[str] = None,
                          user=Depends(require_permission("academicAffairs.scheduleChange.view"))):
    return success(sched_change_svc.stats(user, termId, dimension))


@router.post("/schedule-change/conflict-check", summary="调停课冲突预检（只读，不落库；提交前 UX 反馈）")
def schedule_change_conflict_check(body: ScheduleChangeConflictCheckBody,
                                   user=Depends(require_permission("academicAffairs.scheduleChange.apply"))):
    return success(sched_change_svc.conflict_check(body, user))


@router.get("/schedule-change/archive", summary="调停课归档（仅终态：已生效/已驳回/已撤销，服务层强制过滤）")
def schedule_change_archive(changeType: Optional[str] = None, status: Optional[str] = None,
                            termId: Optional[str] = None, dateFrom: Optional[str] = None,
                            dateTo: Optional[str] = None, page: int = 1, pageSize: int = 20,
                            user=Depends(require_permission("academicAffairs.scheduleChange.view"))):
    items, total = sched_change_svc.archive_list(user, change_type=changeType, status=status,
                                                 term_id=termId, date_from=dateFrom, date_to=dateTo,
                                                 page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


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
    isReselect: bool = Field(False, description="补选场景标志位（仅前端语义提示，后端独立核验资格，见06号卡§10）")


class ExportPurposeBody(BaseModel):
    purpose: str = Field(..., min_length=5, description="导出用途（≥5 字，必填，写审计）")


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


@router.get("/selection/batches/{batchId}/reselect-guide", summary="补选指引（CLOSED 批次，教务处视角）")
def sel_reselect_guide(batchId: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.reselect_guide(user, batchId))


@router.get("/selection/student/reselect-guide", summary="补选指引（学生本人待补选记录+可选课程，06号卡）")
def sel_student_reselect_guide(batchId: Optional[str] = None, user=Depends(_require_student)):
    return success({"items": selection_svc.student_reselect_guide(user, batchId)})


@router.get("/selection/batches/{batchId}/stats", summary="选课统计")
def sel_stats(batchId: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.batch_stats(user, batchId))


@router.get("/selection/batches/{batchId}/conflict-report", summary="冲突预警报表（09号卡，studentNo 可选按学号查询）")
def sel_conflict_report(batchId: int = Path(...), studentNo: Optional[str] = None,
                        user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.get_conflict_report(user, batchId, studentNo))


@router.post("/selection/batches/{batchId}/conflict-report/export", summary="冲突预警报表导出 xlsx（水印+审计+用途必填）")
def sel_conflict_report_export(body: ExportPurposeBody, batchId: int = Path(...),
                               user=Depends(require_permission(_SEL_VIEW))):
    import io

    from fastapi.responses import StreamingResponse
    content = selection_svc.export_conflict_report_xlsx(user, batchId, body.purpose)
    return StreamingResponse(
        io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=selection_conflict_report.xlsx"})


@router.post("/selection/time-tick", summary="定时触发：到点自动开选/截止（供 cron 调度，幂等）")
def sel_time_tick(user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.run_time_tick(user), message="已执行时间触发")


# ── 选课归档（12号卡：ARCHIVED 批次历史查询/导出） ──
@router.get("/selection/archive", summary="归档批次列表（仅 ARCHIVED，12号卡）")
def sel_archive_list(termId: Optional[str] = None, page: int = 1, pageSize: int = 20,
                     user=Depends(require_permission(_SEL_MANAGE))):
    items, total = selection_svc.list_archived_batches(user, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/selection/archive/{batchId}", summary="归档批次详情（含统计，非 ARCHIVED 409）")
def sel_archive_detail(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.archive_detail(user, batchId))


@router.post("/selection/archive/{batchId}/export", summary="归档台账导出 xlsx（水印+审计+用途必填，非 ARCHIVED 409）")
def sel_archive_export(body: ExportPurposeBody, batchId: int = Path(...),
                       user=Depends(require_permission(_SEL_MANAGE))):
    import io

    from fastapi.responses import StreamingResponse
    content = selection_svc.export_archive_xlsx(user, batchId, body.purpose)
    return StreamingResponse(
        io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=selection_archive.xlsx"})
# ── 选课轮次与抽签（多轮次：预选抽签→正选先到先得→补退选；无轮次批次行为不变）──
class SelectionRoundBody(BaseModel):
    roundName: str = Field(..., min_length=1, max_length=100)
    mode: Optional[str] = Field("FCFS", description="FCFS 先到先得 / LOTTERY 抽签")
    allowEnroll: Optional[bool] = True
    allowDrop: Optional[bool] = True


@router.post("/selection/batches/{bid}/rounds", summary="新增选课轮次")
def sel_round_create(body: SelectionRoundBody, bid: int = Path(...),
                     user=Depends(require_permission(_SEL_RULE))):
    return success(selection_round_svc.create_round(user, bid, body), message="已创建轮次")


@router.get("/selection/batches/{bid}/rounds", summary="轮次列表")
def sel_rounds(bid: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success({"items": selection_round_svc.list_rounds(user, bid)})


@router.post("/selection/rounds/{rid}/open", summary="开启轮次（同批次同时仅一个 OPEN）")
def sel_round_open(rid: int = Path(...), user=Depends(require_permission(_SEL_RULE))):
    return success(selection_round_svc.open_round(user, rid), message="轮次已开启")


@router.post("/selection/rounds/{rid}/close", summary="关闭轮次")
def sel_round_close(rid: int = Path(...), user=Depends(require_permission(_SEL_RULE))):
    return success(selection_round_svc.close_round(user, rid), message="轮次已关闭")


@router.post("/selection/rounds/{rid}/draw", summary="抽签摇号（仅 CLOSED 的 LOTTERY 轮，一次性）")
def sel_round_draw(rid: int = Path(...), user=Depends(require_permission(_SEL_RULE))):
    r = selection_round_svc.draw_round(user, rid)
    return success(r, message=f"摇号完成：中签 {r['totalWinners']}，未中签 {r['totalLosers']}")


# ══════════════ 等级考务（/academic-affairs/level-exams/*；四六级/普通话/技能等级证书报名闭环） ══════════════
class LevelExamBody(BaseModel):
    examName: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = Field("SKILL", description="CET/PUTONGHUA/SKILL/OTHER")
    level: Optional[str] = Field(None, max_length=50)
    examDate: Optional[str] = None
    fee: Optional[float] = Field(None, ge=0)
    passLine: Optional[int] = Field(None, ge=0, le=750)


class LevelResultBody(BaseModel):
    score: Optional[int] = Field(None, ge=0, le=750)
    result: Optional[str] = Field(None, description="PASS/FAIL(结论制)")
    certNo: Optional[str] = Field(None, max_length=100)


@router.post("/level-exams", summary="建等级考试")
def level_exam_create(body: LevelExamBody,
                      user=Depends(require_permission("academicAffairs.levelExam.manage"))):
    return success(level_exam_svc.create_exam(user, body), message="已创建")


@router.get("/level-exams", summary="等级考试列表")
def level_exams(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                user=Depends(require_permission("academicAffairs.levelExam.view"))):
    items, total = level_exam_svc.list_exams(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/level-exams/{eid}/transition", summary="状态推进（OPEN 开放报名/CLOSE 截止/FINISH 完成）")
def level_exam_transition(action: str, eid: int = Path(...),
                          user=Depends(require_permission("academicAffairs.levelExam.manage"))):
    return success(level_exam_svc.transition(user, eid, action), message="已推进")


@router.get("/level-exams/{eid}/registrations", summary="报名名单（含缴费/成绩状态）")
def level_exam_regs(eid: int = Path(...), status: Optional[str] = None,
                    page: int = 1, pageSize: int = 100,
                    user=Depends(require_permission("academicAffairs.levelExam.view"))):
    items, total = level_exam_svc.list_regs(user, eid, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/level-exam-regs/{rid}/confirm-fee", summary="缴费确认（UNPAID→PAID）")
def level_fee_confirm(rid: int = Path(...),
                      user=Depends(require_permission("academicAffairs.levelExam.manage"))):
    return success(level_exam_svc.confirm_fee(user, rid), message="已确认缴费")


@router.post("/level-exam-regs/{rid}/result", summary="录入成绩（分数按合格线判/结论制直录；通过可填证书号）")
def level_result(body: LevelResultBody, rid: int = Path(...),
                 user=Depends(require_permission("academicAffairs.levelExam.manage"))):
    return success(level_exam_svc.enter_result(user, rid, body), message="已录入")


# ── 学生端 ──
@router.post("/level-exams/{eid}/register", summary="学生报名等级考试")
def level_student_register(eid: int = Path(...), user=Depends(_require_student)):
    return success(level_exam_svc.student_register(user, eid), message="报名成功")


@router.post("/level-exams/{eid}/cancel", summary="学生取消报名（截止前）")
def level_student_cancel(eid: int = Path(...), user=Depends(_require_student)):
    return success(level_exam_svc.student_cancel(user, eid), message="已取消报名")


@router.get("/level-exams/my", summary="我的等级考试报名与成绩")
def level_my(user=Depends(_require_student)):
    return success({"items": level_exam_svc.my_regs(user)})


# ══════════════ 专业分流（/academic-affairs/major-split/*；大类招生分流：志愿→绩点分配→调剂→写学籍） ══════════════
_SPLIT_MANAGE = "academicAffairs.majorSplit.manage"
_SPLIT_VIEW = "academicAffairs.majorSplit.view"


class SplitBatchBody(BaseModel):
    batchName: str = Field(..., min_length=1, max_length=200)
    grade: str = Field(..., min_length=1, max_length=20)
    sourceMajorId: Optional[str] = None
    maxChoices: Optional[int] = Field(3, ge=1, le=10)


class SplitOptionBody(BaseModel):
    majorId: str = Field(..., min_length=1)
    capacity: int = Field(..., ge=1)


class SplitVolunteerBody(BaseModel):
    choices: list[str] = Field(..., min_length=1, description="志愿序 majorId 数组")


class SplitReassignBody(BaseModel):
    majorId: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=5, max_length=500)


@router.post("/major-split/batches", summary="建专业分流批次")
def split_batch_create(body: SplitBatchBody, user=Depends(require_permission(_SPLIT_MANAGE))):
    return success(major_split_svc.create_batch(user, body), message="已创建")


@router.get("/major-split/batches", summary="分流批次列表")
def split_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                  user=Depends(require_permission(_SPLIT_VIEW))):
    items, total = major_split_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/major-split/batches/{bid}/options", summary="添加可选专业与容量")
def split_option_add(body: SplitOptionBody, bid: int = Path(...),
                     user=Depends(require_permission(_SPLIT_MANAGE))):
    return success(major_split_svc.add_option(user, bid, body), message="已添加")


@router.get("/major-split/batches/{bid}/options", summary="可选专业列表（含余量）")
def split_options(bid: int = Path(...), user=Depends(require_permission(_SPLIT_VIEW))):
    return success({"items": major_split_svc.list_options(user, bid)})


@router.post("/major-split/batches/{bid}/open", summary="开放志愿填报")
def split_open(bid: int = Path(...), user=Depends(require_permission(_SPLIT_MANAGE))):
    return success(major_split_svc.open_batch(user, bid), message="已开放填报")


@router.post("/major-split/batches/{bid}/close", summary="截止志愿")
def split_close(bid: int = Path(...), user=Depends(require_permission(_SPLIT_MANAGE))):
    return success(major_split_svc.close_batch(user, bid), message="已截止")


@router.post("/major-split/batches/{bid}/allocate", summary="自动分配（绩点降序×志愿顺序；dryRun 试分）")
def split_allocate(bid: int = Path(...), dryRun: bool = False,
                   user=Depends(require_permission(_SPLIT_MANAGE))):
    r = major_split_svc.allocate(user, bid, dry_run=dryRun)
    msg = ("试分完成（未落库）" if dryRun
           else f"已分配 {r['allocated']} 人，待调剂 {r['unallocated']} 人")
    return success(r, message=msg)


@router.get("/major-split/batches/{bid}/volunteers", summary="志愿与分配结果名单")
def split_volunteers(bid: int = Path(...), status: Optional[str] = None,
                     page: int = 1, pageSize: int = 100,
                     user=Depends(require_permission(_SPLIT_VIEW))):
    items, total = major_split_svc.list_volunteers(user, bid, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/major-split/volunteers/{vid}/reassign", summary="人工调剂（原因≥5字，容量守护）")
def split_reassign(body: SplitReassignBody, vid: int = Path(...),
                   user=Depends(require_permission(_SPLIT_MANAGE))):
    return success(major_split_svc.reassign(user, vid, body.majorId, body.reason), message="已调剂")


@router.post("/major-split/batches/{bid}/confirm", summary="确认分流（写学籍专业+逐生审计；待调剂未清零禁止）")
def split_confirm(bid: int = Path(...), user=Depends(require_permission(_SPLIT_MANAGE))):
    r = major_split_svc.confirm(user, bid)
    return success(r, message=f"分流已生效 {r['confirmed']} 人")


# ── 学生端 ──
@router.post("/major-split/batches/{bid}/volunteer", summary="学生提交/修改分流志愿")
def split_volunteer_submit(body: SplitVolunteerBody, bid: int = Path(...),
                           user=Depends(_require_student)):
    return success(major_split_svc.submit_volunteer(user, bid, body.choices), message="志愿已提交")


@router.get("/major-split/my", summary="我的分流志愿与结果")
def split_my(batchId: Optional[str] = None, user=Depends(_require_student)):
    return success({"items": major_split_svc.my_volunteer(user, batchId)})


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


# ── 自动排考引擎（编排时间→切考场→铺座位→配监考；dryRun 只算不落）──
class ExamAutoTimesBody(BaseModel):
    dates: list[str] = Field(..., min_length=1, description="考试日期列表 YYYY-MM-DD")
    sessions: list[dict] = Field(..., min_length=1, description="每日场次 [{start:'09:00',end:'11:00'}]")
    maxPerDayPerClass: Optional[int] = Field(1, ge=1, le=4, description="同班每日最多场次")


@router.post("/exam/batches/{bid}/auto-times", summary="自动编排考试时间（日期×场次网格；班级/教师不撞；dryRun 试排）")
def exam_auto_times(body: ExamAutoTimesBody, bid: int = Path(...), dryRun: bool = False,
                    user=Depends(require_permission(_EXAM_ARRANGE))):
    r = autoexam_svc.auto_assign_times(user, bid, body, dry_run=dryRun)
    msg = ("试排完成（未落库）" if dryRun else f"已定时 {r['assigned']} 门，无可用时段 {r['missed']} 门")
    return success(r, message=msg)
@router.post("/exam/batches/{bid}/auto-arrange", summary="自动排考（增量：已有考场的课程跳过）")
def exam_auto_arrange(bid: int = Path(...), dryRun: bool = False,
                      user=Depends(require_permission(_EXAM_ARRANGE))):
    r = autoexam_svc.auto_arrange(user, bid, dry_run=dryRun)
    msg = ("试排完成（未落库）" if dryRun
           else f"已编排 {r['arrangedCourses']} 门，漏排 {r['missedCourses']} 门")
    return success(r, message=msg)


@router.delete("/exam/batches/{bid}/auto-arrange", summary="清除自动排考结果（仅 AUTO 考场，人工编排保留）")
def exam_auto_clear(bid: int = Path(...), user=Depends(require_permission(_EXAM_ARRANGE))):
    return success(autoexam_svc.clear_auto(user, bid), message="已清除自动排考结果")


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


@router.get("/exam/archive", summary="考务归档批次列表（12号卡，只读，ARCHIVED）")
def exam_archive_list(termId: Optional[str] = None, collegeId: Optional[str] = None,
                      page: int = 1, pageSize: int = 20, user=Depends(require_permission(_EXAM_VIEW))):
    items, total = exam_svc.list_archived_batches(user, termId, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


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
_MK_EXPORT = "academicAffairs.makeup.export"
_MK_ARCHIVE = "academicAffairs.makeup.archive"
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


@router.get("/makeup/batches", summary="补考批次列表（kind 可筛 MAKEUP/CLEARANCE）")
def makeup_batches(status: Optional[str] = None, kind: Optional[str] = None,
                   page: int = 1, pageSize: int = 20,
                   user=Depends(require_permission(_MK_VIEW))):
    items, total = makeup_svc.list_makeup_batches(user, status, page, pageSize, kind)
    return success(paginate(items, total, page, pageSize))


# ── 毕业清考（应届生未通过课程的最后考核机会；复用补考审核链与回写，source=CLEARANCE）──
class ClearanceBatchBody(BaseModel):
    batchName: str = Field(..., min_length=1, max_length=200)
    targetGrades: list[str] = Field(..., min_length=1, description="限定毕业年级，如 ['2022']")
    termCode: Optional[str] = None


@router.post("/makeup/clearance/batches", summary="建毕业清考批次（限定毕业年级，计分 CAP60）")
def clearance_batch_create(body: ClearanceBatchBody, user=Depends(require_permission(_MK_MANAGE))):
    return success(makeup_svc.create_clearance_batch(user, body), message="已创建清考批次")


@router.post("/makeup/clearance/batches/{bid}/scan", summary="自动圈定清考名单（最优成绩仍不及格的课程；dryRun 预览）")
def clearance_scan(bid: int = Path(...), dryRun: bool = False,
                   user=Depends(require_permission(_MK_MANAGE))):
    r = makeup_svc.clearance_scan(user, bid, dry_run=dryRun)
    msg = ("预览完成（未落库）" if dryRun else f"已圈定 {r['added']} 条（跳过已存在 {r['skipped']}）")
    return success(r, message=msg)


@router.get("/makeup/clearance/batches/{bid}/records", summary="清考批次名单")
def clearance_records(bid: int = Path(...), page: int = 1, pageSize: int = 100,
                      user=Depends(require_permission(_MK_VIEW))):
    items, total = makeup_svc.clearance_records(user, bid, page, pageSize)
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


# ── 统计分析（三级施工卡 10-统计分析） ──
@router.get("/makeup/stats", summary="补考重修缓考免修四条线统计聚合（人数+通过率，term/collegeId/dimension 可选）")
def makeup_stats(term: Optional[str] = None, collegeId: Optional[str] = None,
                 dimension: Optional[str] = None, user=Depends(require_permission(_MK_VIEW))):
    return success(makeup_svc.aggregate_stats(user, term, collegeId, dimension))


@router.get("/makeup/stats/detail", summary="四条线统计下钻明细（line=makeup/retake/exemption/deferred）")
def makeup_stats_detail(term: Optional[str] = None, collegeId: Optional[str] = None, line: Optional[str] = None,
                        page: int = 1, pageSize: int = 50, user=Depends(require_permission(_MK_VIEW))):
    items, total = makeup_svc.stats_detail(user, term, collegeId, line, page, pageSize)
    return success(paginate(items, total, page, pageSize))


class MakeupStatsExportBody(BaseModel):
    term: Optional[str] = None
    collegeId: Optional[str] = None
    purpose: str = Field(..., min_length=5, description="导出用途（≥5 字，必填，写审计）")


@router.post("/makeup/stats/export", summary="四条线统计导出 xlsx（水印+用途必填+审计）")
def makeup_stats_export(body: MakeupStatsExportBody, user=Depends(require_permission(_MK_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content = makeup_svc.export_makeup_stats_xlsx(user, body.term, body.collegeId, body.purpose)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=makeup_stats.xlsx"})


# ── 材料归档（三级施工卡 11-材料归档） ──
@router.get("/makeup/batches/{bid}/print-data", summary="补考安排表打印页数据（D7）")
def makeup_print_data(bid: int = Path(...), user=Depends(require_permission(_MK_ARCHIVE))):
    return success(makeup_svc.print_data(user, bid))


@router.post("/exemption/{eid}/archive", summary="标记免修材料已归档")
def exemption_archive(eid: int = Path(...), user=Depends(require_permission(_MK_ARCHIVE))):
    return success(makeup_svc.mark_archived(user, eid), message="已标记归档")


@router.get("/exemption/archive-list", summary="免修材料归档列表")
def exemption_archive_list(term: Optional[str] = None, status: Optional[str] = None,
                           page: int = 1, pageSize: int = 50, user=Depends(require_permission(_MK_ARCHIVE))):
    items, total = makeup_svc.archive_list(user, term, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


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


# ══════════════ 排课管理 Tier1 R2 续工（03/05/07/10/11/13 号卡） ══════════════
_SCHED_EDIT = "academicAffairs.schedule.edit"
_SCHED_IMPORT = "academicAffairs.schedule.import"
_SCHED_ARCHIVE = "academicAffairs.schedule.archive"
_SCHED_TEACHER_CONFIRM = "academicAffairs.schedule.teacherConfirm"


class TeacherObjectBody(BaseModel):
    itemId: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=5, max_length=300)


class AdjustItemBody(BaseModel):
    weekday: int = Field(..., ge=1, le=7)
    slotNo: int = Field(..., ge=1)
    classroom: Optional[str] = None
    weekParity: str = Field("ALL")


# ── 05号卡·教室可用时间 ──
@router.get("/schedule-batches/{batchId}/room-view", summary="教室占用查询（05号卡：辅助人工排课选教室）")
def schedule_room_view(batchId: int = Path(...), classroom: str = "",
                       user=Depends(require_permission(_SCHED_VIEW))):
    return success(sched_svc.room_view(batchId, user, classroom))


# ── 10号卡·排课结果 ──
@router.get("/schedule-batches/{batchId}/summary", summary="排课结果汇总统计（10号卡：预发布前核对）")
def schedule_summary(batchId: int = Path(...), user=Depends(require_permission(_SCHED_VIEW))):
    return success(scheduling_svc.summary(user, batchId))


# ── 07号卡·自动排课预留（Excel结果导入通道；不写算法本体） ──
@router.get("/schedule-batches/import/template", summary="排课结果导入模板下载（07号卡）")
def schedule_import_template(user=Depends(require_permission(_SCHED_IMPORT))):
    data = xlsx_util.build_template_xlsx(sched_svc.IMPORT_HEADERS, sample=sched_svc.IMPORT_SAMPLE,
                                         notes=sched_svc.IMPORT_NOTES, required=sched_svc.IMPORT_REQUIRED)
    return StreamingResponse(io.BytesIO(data), media_type=_XLSX_MEDIA, headers={
        "Content-Disposition": "attachment; filename=schedule_import_template.xlsx"})


@router.post("/schedule-batches/{batchId}/import/xlsx", summary="上传Excel导入排课结果（07号卡：自动排课预留=结果导入通道）")
async def schedule_import_xlsx(batchId: int = Path(...), file: UploadFile = File(...),
                               user=Depends(require_permission(_SCHED_IMPORT))):
    content = await file.read()
    rows = xlsx_util.read_xlsx(content, sched_svc.IMPORT_HEADER_MAP)
    if len(rows) > sched_svc.IMPORT_MAX_ROWS:
        raise AppException("VALIDATION_ERROR", f"单批导入行数不得超过 {sched_svc.IMPORT_MAX_ROWS} 行")
    rows = sched_svc.sanitize_import_rows(rows)
    return success(sched_svc.import_items(batchId, user, rows), message="导入完成")


# ── 11号卡·排课调整（预发布阶段教师异议 → 定点改排） ──
@router.post("/schedule-batches/{batchId}/teacher-object", summary="教师对本人课表提出异议（11号卡）")
def schedule_teacher_object(body: TeacherObjectBody, batchId: int = Path(...),
                            user=Depends(require_permission(_SCHED_TEACHER_CONFIRM))):
    return success(sched_svc.teacher_object(batchId, user, body.itemId, body.reason), message="异议已提交")


@router.get("/schedule-batches/{batchId}/objections", summary="本批次待处理教师异议清单（11号卡）")
def schedule_objections(batchId: int = Path(...), user=Depends(require_permission(_SCHED_VIEW))):
    return success({"items": sched_svc.list_objections(batchId, user)})


@router.put("/schedule-batches/{batchId}/items/{itemId}", summary="排课调整（11号卡：处理教师异议定点改排）")
def schedule_adjust_item(body: AdjustItemBody, batchId: int = Path(...), itemId: int = Path(...),
                         user=Depends(require_permission(_SCHED_EDIT))):
    return success(sched_svc.adjust_item(batchId, itemId, user, body.weekday, body.slotNo,
                                         body.classroom, body.weekParity), message="已改排")


# ── 13号卡·排课归档（区别于 void-reissue 应急作废重排） ──
@router.post("/schedule-batches/{batchId}/archive", summary="排课归档（13号卡：学期结束正式归档）")
def schedule_archive(batchId: int = Path(...), user=Depends(require_permission(_SCHED_ARCHIVE))):
    return success(sched_svc.archive(batchId, user), message="已归档")
# ── 自动排课引擎（参数→编排→漏排归因→迭代续排）──
@router.get("/scheduling/rule-catalog", summary="排课参数说明书（供参数面板渲染）")
def sched_rule_catalog(user=Depends(require_permission(_SCHED_VIEW))):
    return success(autosched_svc.rule_catalog(user))


@router.get("/scheduling/batches/{bid}/miss-report", summary="漏排数据分析（只读试排，不落库）")
def sched_miss_report(bid: int = Path(...), user=Depends(require_permission(_SCHED_VIEW))):
    return success(autosched_svc.miss_report(user, bid))


@router.post("/scheduling/batches/{bid}/auto", summary="自动编排课表（增量续排；dryRun 只算不落）")
def sched_auto(bid: int = Path(...), dryRun: bool = False,
               user=Depends(require_permission(_SCHED_RULE))):
    r = autosched_svc.auto_schedule(user, bid, dry_run=dryRun)
    msg = ("试排完成（未落库）" if dryRun
           else f"已排入 {r['placedSessions']} 节，漏排 {r['missedTasks']} 个任务")
    return success(r, message=msg)


@router.delete("/scheduling/batches/{bid}/auto", summary="清除自动排课结果（仅 AUTO 项，人工排课保留）")
def sched_auto_clear(bid: int = Path(...), user=Depends(require_permission(_SCHED_RULE))):
    return success(autosched_svc.clear_auto_items(user, bid), message="已清除自动排课结果")


# ══════════════ 教学评价（13B，/academic-affairs/evaluation/*） ══════════════
_EVAL_MANAGE = "academicAffairs.evaluation.batch.manage"
_EVAL_VIEW = "academicAffairs.evaluation.view"
_EVAL_APPEAL = "academicAffairs.evaluation.appeal.review"
# Tier1 R2 新增（学生评教PC查看/教师自评/同行评价/督导评价/评价统计导出/评价归档导出）：
# 沿用既有代码现状——本文件全部端点权限码均未在 ROLE_PERMISSIONS 逐条注册，而是命中角色已授予的
# "academicAffairs.*" 通配（ACADEMIC_ADMIN/ACADEMIC_TEACHER 均持有该通配，见 backend/app/core/permissions.py:50-51）；
# 真正的"是否本人评价任务"越权拦截在 service 层按 evaluator_key/_derive_keys 实例化（见 §10 权限矩阵设计），
# 不新增 ROLE_PERMISSIONS 角色行（避免与并行子任务共同修改该共享文件冲突，亦无督导专属角色可挂）。
_EVAL_ROLE_MANAGE = "academicAffairs.evaluation.batch.manage"
_EVAL_EXPORT = "academicAffairs.evaluation.export"


class EvalBatchBody(BaseModel):
    batchName: str = Field(..., min_length=1)
    termId: Optional[str] = None
    scope: Optional[dict] = None
    template: Optional[dict] = None
    anonymous: Optional[bool] = True


class EvalGenTasksBody(BaseModel):
    teachingTaskIds: list[str] = Field(default_factory=list)
    evaluatorType: str = Field("STUDENT", description="STUDENT/SELF/PEER/SUPERVISOR")


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


class EvalRoleAssignment(BaseModel):
    teachingTaskId: str = Field(..., min_length=1)
    evaluatorKey: Optional[str] = Field(None, max_length=100, description="PEER/SUPERVISOR必填；SELF缺省=授课教师本人")


class EvalRoleGenBody(BaseModel):
    evaluatorType: str = Field(..., description="SELF/PEER/SUPERVISOR")
    assignments: List[EvalRoleAssignment] = Field(default_factory=list)


class EvalExportBody(BaseModel):
    domain: str = Field(..., description="results/stats")
    purpose: str = Field(..., min_length=5, max_length=200)


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
    return success(evaluation_svc.generate_tasks(user, bid, body.teachingTaskIds, body.evaluatorType),
                   message="已生成")


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


# ── 教师自评/同行评价/督导评价：生成应评任务 + 查看我的任务 ──
@router.post("/evaluation/batches/{bid}/role-tasks", summary="生成教师自评/同行评价/督导评价应评任务")
def eval_role_tasks(body: EvalRoleGenBody, bid: int = Path(...), user=Depends(require_permission(_EVAL_ROLE_MANAGE))):
    assignments = [a.model_dump() for a in body.assignments]
    return success(evaluation_svc.generate_role_tasks(user, bid, body.evaluatorType, assignments), message="已生成")


@router.get("/evaluation/my-role-tasks", summary="我的评价任务（自评/同行/督导，按登录身份匹配 evaluatorKey）")
def eval_my_role_tasks(evaluatorType: str, batchId: Optional[str] = None, user=Depends(require_staff)):
    return success({"items": evaluation_svc.list_my_role_tasks(user, evaluatorType, batchId)})


# ── 提交评价（学生匿名/教师自评/同行/督导；越权与重复提交校验见 service 层） ──
@router.post("/evaluation/submit", summary="提交评价（学生匿名不存身份；自评/同行/督导校验本人）")
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


@router.get("/evaluation/batches/{bid}/stats", summary="评价统计（结果分级+按评价类型参评率）")
def eval_stats(bid: int = Path(...), user=Depends(require_permission(_EVAL_VIEW))):
    return success(evaluation_svc.stats(user, bid))


@router.post("/evaluation/batches/{bid}/export", summary="导出评价结果/参评统计 xlsx（评价统计/评价归档共用）")
def eval_export(body: EvalExportBody, bid: int = Path(...), user=Depends(require_permission(_EVAL_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content = evaluation_svc.export_evaluation_xlsx(user, bid, body.domain, body.purpose)
    return StreamingResponse(io.BytesIO(content),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=evaluation_{body.domain}_{bid}.xlsx"})


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


# ══════════════ 教学质量 R3 续工（01督导听课/02巡课/03检查/04事故/05整改/06跟进/09归档） ══════════════
# 01/02/03/04 共用 /quality/records（recordType 判别）；05/06 共用 /quality/rectifications；
# 09 只读聚合 /quality/archive/*，零新表。权限点命名延续既有 academicAffairs.quality.* 风格。
_QREC_VIEW = "academicAffairs.quality.record.view"
_QREC_MANAGE = "academicAffairs.quality.record.manage"
_QINCIDENT_MANAGE = "academicAffairs.quality.incident.manage"
_QRECT_VIEW = "academicAffairs.quality.rectification.view"
_QRECT_MANAGE = "academicAffairs.quality.rectification.manage"
_QARCHIVE_VIEW = "academicAffairs.quality.archive.view"
_QARCHIVE_EXPORT = "academicAffairs.quality.archive.export"


class QualityRecordCreate(BaseModel):
    recordType: str = Field(..., description="SUPERVISION/PATROL/INSPECTION/INCIDENT")
    title: str = Field(..., min_length=1)
    termId: Optional[str] = None
    collegeId: Optional[str] = None
    majorId: Optional[str] = None
    classId: Optional[str] = None
    teacherKey: Optional[str] = None
    teacherName: Optional[str] = None
    courseId: Optional[str] = None
    courseName: Optional[str] = None
    occurredAt: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    score: Optional[float] = None
    conclusion: Optional[str] = None
    description: Optional[str] = None
    handlingNote: Optional[str] = None
    needRectify: Optional[bool] = False


class QualityRecordUpdate(BaseModel):
    title: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    conclusion: Optional[str] = None
    description: Optional[str] = None
    handlingNote: Optional[str] = None
    teacherName: Optional[str] = None
    courseName: Optional[str] = None
    score: Optional[float] = None
    needRectify: Optional[bool] = None
    collegeId: Optional[str] = None


class RectificationCreate(BaseModel):
    title: str = Field(..., min_length=1)
    requirement: str = Field(..., min_length=5, description="整改要求，写审计")
    sourceRecordId: Optional[str] = None
    termId: Optional[str] = None
    collegeId: Optional[str] = None
    majorId: Optional[str] = None
    classId: Optional[str] = None
    deadline: Optional[str] = None
    responsibleKey: Optional[str] = None
    responsibleName: Optional[str] = None


class RectificationNoteBody(BaseModel):
    note: str = Field(..., min_length=2)


class RectificationReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    reason: Optional[str] = ""


@router.get("/quality/records", summary="质量问题记录列表（督导听课/巡课/检查/事故，recordType筛选）")
def quality_record_list(recordType: Optional[str] = None, termId: Optional[str] = None,
                        collegeId: Optional[str] = None, status: Optional[str] = None,
                        teacherKey: Optional[str] = None, page: int = 1, pageSize: int = 20,
                        user=Depends(require_permission(_QREC_VIEW))):
    items, total = quality_svc.list_records(user, recordType, termId, collegeId, status, teacherKey, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/quality/records", summary="新建质量问题记录")
def quality_record_create(body: QualityRecordCreate, user=Depends(require_permission(_QREC_MANAGE))):
    if (body.recordType or "").strip().upper() == "INCIDENT":
        enforce_permission(user, _QINCIDENT_MANAGE)  # 教学事故上报额外要求 incident.manage（04号卡红线）
    return success(quality_svc.create_record(user, body), message="已创建")


@router.get("/quality/records/{rid}", summary="质量问题记录详情")
def quality_record_detail(rid: int = Path(...), user=Depends(require_permission(_QREC_VIEW))):
    return success(quality_svc.get_record(user, rid))


@router.put("/quality/records/{rid}", summary="编辑质量问题记录（仅SUBMITTED阶段）")
def quality_record_update(body: QualityRecordUpdate, rid: int = Path(...), user=Depends(require_permission(_QREC_MANAGE))):
    return success(quality_svc.update_record(user, rid, body), message="已保存")


@router.post("/quality/records/{rid}/confirm", summary="确认质量问题记录（教学事故认定仅限全校范围角色）")
def quality_record_confirm(rid: int = Path(...), user=Depends(require_permission(_QREC_MANAGE))):
    return success(quality_svc.confirm_record(user, rid), message="已确认")


@router.post("/quality/records/{rid}/close", summary="关闭质量问题记录")
def quality_record_close(rid: int = Path(...), user=Depends(require_permission(_QREC_MANAGE))):
    return success(quality_svc.close_record(user, rid), message="已关闭")


@router.delete("/quality/records/{rid}", summary="撤销质量问题记录（仅SUBMITTED阶段，软删）")
def quality_record_cancel(rid: int = Path(...), user=Depends(require_permission(_QREC_MANAGE))):
    return success(quality_svc.cancel_record(user, rid), message="已撤销")


@router.get("/quality/rectifications", summary="质量整改任务列表（发起视角+跟进视角共用）")
def quality_rect_list(status: Optional[str] = None, termId: Optional[str] = None, collegeId: Optional[str] = None,
                      sourceType: Optional[str] = None, overdue: Optional[bool] = None,
                      page: int = 1, pageSize: int = 20, user=Depends(require_permission(_QRECT_VIEW))):
    items, total = quality_svc.list_rectifications(user, status, termId, collegeId, sourceType, overdue, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/quality/rectifications", summary="发起质量整改任务（可关联来源问题记录）")
def quality_rect_create(body: RectificationCreate, user=Depends(require_permission(_QRECT_MANAGE))):
    return success(quality_svc.create_rectification(user, body), message="已发起")


@router.post("/quality/records/{rid}/rectify", summary="从问题记录一键发起整改（快捷入口）")
def quality_record_rectify(body: RectificationCreate, rid: int = Path(...), user=Depends(require_permission(_QRECT_MANAGE))):
    body.sourceRecordId = str(rid)
    return success(quality_svc.create_rectification(user, body), message="已发起")


@router.get("/quality/rectifications/{rid}", summary="整改任务详情（含跟进时间线）")
def quality_rect_detail(rid: int = Path(...), user=Depends(require_permission(_QRECT_VIEW))):
    return success(quality_svc.get_rectification(user, rid))


@router.post("/quality/rectifications/{rid}/progress", summary="记录整改跟进（06号卡核心动作）")
def quality_rect_progress(body: RectificationNoteBody, rid: int = Path(...), user=Depends(require_permission(_QRECT_MANAGE))):
    return success(quality_svc.add_progress(user, rid, body.note), message="已记录")


@router.post("/quality/rectifications/{rid}/submit", summary="提交整改说明待复核")
def quality_rect_submit(body: RectificationNoteBody, rid: int = Path(...), user=Depends(require_permission(_QRECT_MANAGE))):
    return success(quality_svc.submit_rectification(user, rid, body.note), message="已提交")


@router.post("/quality/rectifications/{rid}/review", summary="复核整改（通过关闭/驳回重新整改，仅全校范围角色）")
def quality_rect_review(body: RectificationReviewBody, rid: int = Path(...), user=Depends(require_permission(_QRECT_MANAGE))):
    return success(quality_svc.review_rectification(user, rid, body.action, body.reason), message="已复核")


@router.get("/quality/archive/overview", summary="质量归档总览（09号卡：按学期聚合01-06六类问题记录+整改统计）")
def quality_archive_overview(termId: Optional[str] = None, user=Depends(require_permission(_QARCHIVE_VIEW))):
    return success(quality_svc.archive_overview(user, termId))


@router.get("/quality/archive/export", summary="质量归档导出xlsx（domain=records|rectifications）")
def quality_archive_export(domain: str, termId: Optional[str] = None, purpose: str = "",
                           user=Depends(require_permission(_QARCHIVE_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content = quality_svc.archive_export(user, domain, termId, purpose)
    return StreamingResponse(io.BytesIO(content),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=quality_archive_{domain}.xlsx"})


# ══════════════ 教务归档（13B-R7，/academic-affairs/archive/*） ══════════════
_ARCHIVE_MANAGE = "academicAffairs.archive.manage"
_ARCHIVE_VIEW = "academicAffairs.archive.view"
_ARCHIVE_EXPORT = "academicAffairs.archive.export"


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


@router.get("/archive/precheck", summary="归档缺失提醒：9域实时预检查（不落库）")
def archive_precheck(termId: Optional[str] = None, user=Depends(require_permission(_ARCHIVE_VIEW))):
    return success(archive_svc.precheck(user, termId))


@router.get("/archive/batches/{bid}/download-log", summary="归档下载记录查询")
def archive_download_log(bid: int = Path(...), user=Depends(require_permission(_ARCHIVE_VIEW))):
    return success(archive_svc.list_download_log(user, bid))


@router.get("/archive/batches/{bid}/export", summary="打包下载全部归档物料（zip）")
def archive_export_all(bid: int = Path(...), purpose: str = "", user=Depends(require_permission(_ARCHIVE_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content, filename = archive_svc.export_batch_all(user, bid, purpose)
    return StreamingResponse(io.BytesIO(content), media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/archive/batches/{bid}/items/{category}/export", summary="单数据域水印导出")
def archive_export_item(bid: int = Path(...), category: str = Path(...), purpose: str = "",
                        user=Depends(require_permission(_ARCHIVE_EXPORT))):
    import io

    from fastapi.responses import StreamingResponse
    content, filename = archive_svc.export_batch_item(user, bid, category, purpose)
    return StreamingResponse(io.BytesIO(content),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})
