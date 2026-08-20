"""微信小程序性能收口路由。"""
from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.response import success
from app.core.security import get_current_user, require_staff
from app.services import mobile_observability_service as mobile_obs
from app.services import mobile_performance_service as service
from app.services import teacher_mobile_messages_v3_service as teacher_messages_v3
from app.services import teacher_mobile_workbench_v3_service as teacher_workbench_v3


router = APIRouter(prefix="/mobile/performance", tags=["mobile-performance"])


class MessageReadBatchBody(BaseModel):
    messageIds: list[str] = Field(default_factory=list)


def _observe_teacher_message_read(started: float, user: dict) -> None:
    """T10 anonymous observability; never emit title/content/user identifiers."""
    mobile_obs.record_latency("pageLatency", (perf_counter() - started) * 1000.0)
    mobile_obs.record(
        "scopeMode",
        "MESSAGE_CONTEXT" if str((user or {}).get("activeContextId") or "").strip() else "MESSAGE_GLOBAL",
    )


@router.get("/teacher/workbench", summary="教师移动工作台单请求快照")
def teacher_workbench(
    page_size: int = Query(default=8, alias="pageSize", ge=1, le=20),
    user=Depends(require_staff),
):
    return success(teacher_workbench_v3.teacher_workbench(user, page_size=page_size))


@router.get("/teacher/todos-page", summary="教师待办数据库分页")
def teacher_todos_page(
    group: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    user=Depends(require_staff),
):
    return success(service.teacher_todos_page(
        user, group=group, page=page, page_size=page_size
    ))


@router.get("/teacher/risk-students-page", summary="教师风险学生数据库分页")
def teacher_risk_students_page(
    level: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    user=Depends(require_staff),
):
    return success(service.teacher_risk_students_page(
        user, level=level, page=page, page_size=page_size
    ))


@router.get("/teacher/messages-page", summary="教师消息 eventAt/id 真网络分页")
def teacher_messages_page(
    tab: str = Query(default="system", max_length=20),
    cursor: str | None = Query(default=None, max_length=2048),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    q: str = Query(default="", max_length=40),
    user=Depends(require_staff),
):
    started = perf_counter()
    try:
        return success(teacher_messages_v3.list_messages(
            user, tab=tab, cursor=cursor, page_size=page_size, q=q
        ))
    finally:
        _observe_teacher_message_read(started, user)


@router.get("/teacher/messages-badges", summary="教师消息未读分类独立聚合")
def teacher_messages_badges(user=Depends(require_staff)):
    started = perf_counter()
    try:
        return success(teacher_messages_v3.unread_badges(user))
    finally:
        _observe_teacher_message_read(started, user)


@router.get("/teacher/messages/{message_id}", summary="教师消息详情（本人收件箱范围）")
def teacher_message_detail(message_id: str, user=Depends(require_staff)):
    return success(teacher_messages_v3.get_message(user, message_id))


@router.post("/teacher/messages/{message_id}/receipt", summary="教师消息确认回执")
def teacher_message_receipt(message_id: str, user=Depends(require_staff)):
    return success(teacher_messages_v3.ack_message(user, message_id), message="已确认")


@router.get("/student/messages-page", summary="学生消息数据库分页")
def student_messages_page(
    tab: str = Query(default="todo"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    user=Depends(get_current_user),
):
    return success(service.student_messages_page(
        user, tab=tab, page=page, page_size=page_size
    ))


@router.post("/student/messages/read-batch", summary="学生消息批量已读")
def student_messages_read_batch(
    body: MessageReadBatchBody,
    user=Depends(get_current_user),
):
    return success(service.read_messages_batch(user, body.messageIds))
