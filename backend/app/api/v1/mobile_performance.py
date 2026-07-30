"""微信小程序性能收口路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.response import success
from app.core.security import get_current_user, require_staff
from app.services import mobile_performance_service as service


router = APIRouter(prefix="/mobile/performance", tags=["mobile-performance"])


class MessageReadBatchBody(BaseModel):
    messageIds: list[str] = Field(default_factory=list)


@router.get("/teacher/workbench", summary="教师移动工作台单请求快照")
def teacher_workbench(
    page_size: int = Query(default=8, alias="pageSize", ge=1, le=20),
    user=Depends(require_staff),
):
    return success(service.teacher_workbench(user, page_size=page_size))


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
