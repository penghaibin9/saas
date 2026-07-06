"""13B 教务中心 API（/api/v1/academic-affairs/*）—— P1：首页 + 学年学期/校历/节次 + 学籍名册 + 入学注册。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.response import paginate, success
from app.core.security import require_staff
from app.services import academic_affairs_service as svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])


@router.get("/dashboard", summary="教务首页（当前学期 + 模块卡）")
def dashboard(user=Depends(require_staff)):
    return success(svc.dashboard(user))


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


@router.get("/registration-batches", summary="注册批次列表")
def reg_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = svc.list_registration_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/register", summary="学生注册（经 change_student_status 单一入口）")
def register(body: RegisterBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(svc.register_student(batchId, user, body.studentId), message="注册成功")


@router.get("/registration-batches/{batchId}/registrations", summary="注册记录列表")
def registrations(batchId: int = Path(...), page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = svc.list_registrations(batchId, user, page, pageSize)
    return success(paginate(items, total, page, pageSize))
