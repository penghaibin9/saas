"""D1-S 学期、校历、作息节次与 time-bands 的正式 Router。

本模块是纯结构迁移：URL、HTTP method、DTO、permission、参数默认值、
状态码和 service 调用全部沿用历史 ``academic_affairs`` 合同。
历史模块中的 DTO/端点暂保留为兼容来源；公开聚合器优先挂载本 Router，
由 normalized method/path 去重确保生产请求只命中这里。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import academic_affairs_service as svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

_TERM_VIEW = "academicAffairs.term.view"
_TERM_MANAGE = "academicAffairs.term.manage"

# D1-S Move Only：复用历史 DTO 对象，避免结构迁移改变 Pydantic/OpenAPI 合同。
TermCreate = legacy.TermCreate
TeachingWeeksBody = legacy.TeachingWeeksBody
TermUnfreezeBody = legacy.TermUnfreezeBody
CalendarEventBody = legacy.CalendarEventBody
CalendarEventUpdate = legacy.CalendarEventUpdate
TimeSlotCreate = legacy.TimeSlotCreate
TimeSlotUpdate = legacy.TimeSlotUpdate
TimeBandCreate = legacy.TimeBandCreate
TimeBandUpdate = legacy.TimeBandUpdate


@router.post("/terms", summary="新建学年学期")
def term_create(body: TermCreate, user=Depends(require_permission(_TERM_MANAGE))):
    return success(svc.create_term(body, user), message="已创建")


@router.get("/terms", summary="学期列表")
def terms(
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission(_TERM_VIEW)),
):
    items, total = svc.list_terms(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/terms/current", summary="当前学期")
def term_current(user=Depends(require_permission(_TERM_VIEW))):
    return success(svc.current_term(user))


@router.post("/terms/{termId}/publish", summary="发布学期（设为当前，幂等）")
def term_publish(termId: int = Path(...), user=Depends(require_permission(_TERM_MANAGE))):
    return success(svc.publish_term(termId, user), message="已发布")


@router.post("/terms/{termId}/set-current", summary="当前学期设置：设为当前学期（仅 PUBLISHED，幂等）")
def term_set_current(termId: int = Path(...), user=Depends(require_permission(_TERM_MANAGE))):
    return success(svc.set_current_term(termId, user), message="已设为当前学期")


@router.get("/terms/{termId}/weeks", summary="学期周次（按开学日+教学周展开，叠加校历事件）")
def term_weeks(termId: int = Path(...), user=Depends(require_permission(_TERM_VIEW))):
    return success({"items": svc.list_term_weeks(termId, user)})


@router.put("/terms/{termId}/teaching-weeks", summary="教学周配置（仅 DRAFT 学期可调整结构）")
def term_teaching_weeks_update(
    body: TeachingWeeksBody,
    termId: int = Path(...),
    user=Depends(require_permission(_TERM_MANAGE)),
):
    return success(svc.update_teaching_weeks(termId, body, user), message="已保存")


@router.post("/terms/{termId}/freeze", summary="学期状态·冻结（PUBLISHED→FROZEN）")
def term_freeze(termId: int = Path(...), user=Depends(require_permission(_TERM_MANAGE))):
    return success(svc.freeze_term(termId, user), message="已冻结")


@router.post("/terms/{termId}/unfreeze", summary="学期状态·解冻（FROZEN→PUBLISHED，原因≥5字）")
def term_unfreeze(
    body: TermUnfreezeBody,
    termId: int = Path(...),
    user=Depends(require_permission(_TERM_MANAGE)),
):
    return success(svc.unfreeze_term(termId, body.reason, user), message="已解冻")


# 字面量路径必须先于 /terms/{termId}，保持历史 FastAPI 匹配顺序。
@router.get("/terms/archive-overview", summary="学期归档总览（只读，实际归档动作见教务归档模块）")
def terms_archive_overview(user=Depends(require_permission(_TERM_VIEW))):
    return success({"items": svc.term_archive_overview(user)})


@router.get("/terms/years", summary="学年管理：按学年汇总学期（只读聚合，不新建表）")
def terms_years(user=Depends(require_permission(_TERM_VIEW))):
    return success({"items": svc.list_academic_years(user)})


@router.get("/terms/switch-log", summary="学期切换记录：当前学期切换审计（PUBLISH/SET_CURRENT 流水推导）")
def terms_switch_log(
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission(_TERM_VIEW)),
):
    items, total = svc.list_term_switch_log(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/terms/{termId}", summary="学期详情（校历/作息等只读联动查看复用）")
def term_detail(termId: int = Path(...), user=Depends(require_permission(_TERM_VIEW))):
    return success(svc.term_detail(termId, user))


@router.post("/terms/{termId}/calendar", summary="添加校历事件（节假日/补课日/教学/考试/实习）")
def calendar_add(
    body: CalendarEventBody,
    termId: int = Path(...),
    user=Depends(require_permission("academicAffairs.calendar.manage")),
):
    return success(svc.add_calendar_event(termId, user, body), message="已添加")


@router.get("/terms/{termId}/calendar", summary="校历事件列表（可按 eventType 过滤：HOLIDAY 节假日/SWAP 补课日）")
def calendar_list(
    termId: int = Path(...),
    eventType: Optional[str] = None,
    user=Depends(require_permission("academicAffairs.calendar.view")),
):
    return success({"items": svc.list_calendar(termId, user, eventType)})


@router.put("/terms/{termId}/calendar/{eventId}", summary="编辑校历事件（发布后锁定 409）")
def calendar_update(
    body: CalendarEventUpdate,
    termId: int = Path(...),
    eventId: int = Path(...),
    user=Depends(require_permission("academicAffairs.calendar.manage")),
):
    return success(svc.update_calendar_event(termId, eventId, user, body), message="已保存")


@router.delete("/terms/{termId}/calendar/{eventId}", summary="删除校历事件（发布后锁定 409）")
def calendar_delete(
    termId: int = Path(...),
    eventId: int = Path(...),
    user=Depends(require_permission("academicAffairs.calendar.manage")),
):
    return success(svc.delete_calendar_event(termId, eventId, user), message="已删除")


@router.get("/terms/{termId}/week-calendar", summary="教学周日历（周次×周类型聚合，叠加节假日/补课日着色）")
def week_calendar(
    termId: int = Path(...),
    user=Depends(require_permission("academicAffairs.calendar.view")),
):
    return success(svc.week_calendar(termId, user))


@router.post("/terms/{termId}/calendar/publish", summary="发布校历（校验节次已配置+补课日已配对，仅教务处/学校管理员）")
def calendar_publish(
    termId: int = Path(...),
    user=Depends(require_permission("academicAffairs.calendarPublish.manage")),
):
    return success(svc.publish_calendar(termId, user), message="已发布")


@router.post("/time-slots", summary="新建作息节次")
def time_slot_create(
    body: TimeSlotCreate,
    user=Depends(require_permission("academicAffairs.timeslot.manage")),
):
    return success(svc.create_time_slot(body, user), message="已创建")


@router.get("/time-slots", summary="作息节次列表（includeDisabled=true 含已停用，供节次管理页）")
def time_slots(
    includeDisabled: bool = False,
    user=Depends(require_permission("academicAffairs.timeslot.view")),
):
    return success({"items": svc.list_time_slots(user, includeDisabled)})


@router.put("/time-slots/{slotId}", summary="编辑作息节次（含启用/停用）")
def time_slot_update(
    body: TimeSlotUpdate,
    slotId: int = Path(...),
    user=Depends(require_permission("academicAffairs.timeslot.manage")),
):
    return success(svc.update_time_slot(slotId, user, body), message="已保存")


@router.delete("/time-slots/{slotId}", summary="删除作息节次（逻辑删除）")
def time_slot_delete(
    slotId: int = Path(...),
    user=Depends(require_permission("academicAffairs.timeslot.manage")),
):
    return success(svc.delete_time_slot(slotId, user), message="已删除")


@router.post("/time-slots/{slotId}/time-bands", summary="新建上课时间段（绑定节次的实际钟点）")
def time_band_create(
    body: TimeBandCreate,
    slotId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classTimeBand.manage")),
):
    return success(svc.create_time_band(slotId, user, body), message="已创建")


@router.get("/time-slots/{slotId}/time-bands", summary="上课时间段列表（按节次）")
def time_band_list(
    slotId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classTimeBand.view")),
):
    return success({"items": svc.list_time_bands(slotId, user)})


@router.put("/time-bands/{bandId}", summary="编辑上课时间段")
def time_band_update(
    body: TimeBandUpdate,
    bandId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classTimeBand.manage")),
):
    return success(svc.update_time_band(bandId, user, body), message="已保存")


@router.delete("/time-bands/{bandId}", summary="删除上课时间段")
def time_band_delete(
    bandId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classTimeBand.manage")),
):
    return success(svc.delete_time_band(bandId, user), message="已删除")
