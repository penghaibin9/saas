"""D5-S4 调停课 Move Only Router。

只迁出 legacy 大 Router 已有的调课/停课/补课申请、预检、审批、撤销、归档与统计入口。
DTO、权限依赖、sched_change_svc 与状态机全部复用原合同，不改变审批或课表改写语义。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-调停课"])

ScheduleChangeSubmit = legacy.ScheduleChangeSubmit
ScheduleChangeReviewBody = legacy.ScheduleChangeReviewBody
ScheduleChangeCancelBody = legacy.ScheduleChangeCancelBody
ScheduleChangeConflictCheckBody = legacy.ScheduleChangeConflictCheckBody
sched_change_svc = legacy.sched_change_svc
_SC_REVIEW = legacy._SC_REVIEW


@router.post("/schedule-change", summary="发起调停课（提交即目标冲突预检；冲突单据不落库）")
def schedule_change_submit(
    body: ScheduleChangeSubmit,
    user=Depends(require_permission("academicAffairs.scheduleChange.apply")),
):
    return success(sched_change_svc.submit(body, user), message="调停课已提交")


@router.get("/schedule-change", summary="调停课台账（范围过滤）")
def schedule_change_list(
    changeType: Optional[str] = None,
    status: Optional[str] = None,
    teacherKey: Optional[str] = None,
    termId: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.scheduleChange.view")),
):
    items, total = sched_change_svc.list_changes(
        user,
        change_type=changeType,
        status=status,
        teacher_key=teacherKey,
        term_id=termId,
        page=page,
        page_size=pageSize,
    )
    return success(paginate(items, total, page, pageSize))


# GET 字面量路径必须先于 /schedule-change/{changeId}。
@router.get("/schedule-change/stats", summary="调停课统计（按类型/状态/学院/教师聚合）")
def schedule_change_stats(
    termId: Optional[str] = None,
    dimension: Optional[str] = None,
    user=Depends(require_permission("academicAffairs.scheduleChange.view")),
):
    return success(sched_change_svc.stats(user, termId, dimension))


@router.post("/schedule-change/conflict-check", summary="调停课冲突预检（只读，不落库；提交前 UX 反馈）")
def schedule_change_conflict_check(
    body: ScheduleChangeConflictCheckBody,
    user=Depends(require_permission("academicAffairs.scheduleChange.apply")),
):
    return success(sched_change_svc.conflict_check(body, user))


@router.get("/schedule-change/archive", summary="调停课归档（仅终态：已生效/已驳回/已撤销，服务层强制过滤）")
def schedule_change_archive(
    changeType: Optional[str] = None,
    status: Optional[str] = None,
    termId: Optional[str] = None,
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.scheduleChange.view")),
):
    items, total = sched_change_svc.archive_list(
        user,
        change_type=changeType,
        status=status,
        term_id=termId,
        date_from=dateFrom,
        date_to=dateTo,
        page=page,
        page_size=pageSize,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/schedule-change/{changeId}", summary="调停课详情（含通知单打印数据）")
def schedule_change_detail(
    changeId: int = Path(...),
    user=Depends(require_permission("academicAffairs.scheduleChange.view")),
):
    return success(sched_change_svc.get_change(changeId, user))


@router.post("/schedule-change/{changeId}/approve", summary="审批通过（学院/教务处；终审通过即改写课表）")
def schedule_change_approve(
    body: ScheduleChangeReviewBody = ScheduleChangeReviewBody(action="APPROVE"),
    changeId: int = Path(...),
    user=Depends(_SC_REVIEW),
):
    return success(sched_change_svc.review(changeId, user, "APPROVE", body.comment or ""), message="已通过")


@router.post("/schedule-change/{changeId}/reject", summary="驳回（原因≥5 字）")
def schedule_change_reject(
    body: ScheduleChangeReviewBody,
    changeId: int = Path(...),
    user=Depends(_SC_REVIEW),
):
    return success(sched_change_svc.review(changeId, user, "REJECT", body.comment or ""), message="已驳回")


@router.post("/schedule-change/{changeId}/cancel", summary="撤销（仅 SUBMITTED/COLLEGE_REVIEW，APPROVED 后 409）")
def schedule_change_cancel(
    body: ScheduleChangeCancelBody = ScheduleChangeCancelBody(),
    changeId: int = Path(...),
    user=Depends(require_permission("academicAffairs.scheduleChange.apply")),
):
    return success(sched_change_svc.cancel(changeId, user, body.reason or ""), message="已撤销")
