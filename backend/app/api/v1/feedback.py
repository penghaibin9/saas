"""帮助与反馈工单 API（历史欠账收口：t_feedback 表早有，此前 0 端点）。

提交侧（任意登录用户，本人）：POST /feedback、GET /feedback/my。
处理侧（学工/管理角色，按租户）：GET /feedback、GET /feedback/stats、
GET /feedback/{id}、POST /feedback/{id}/handle。
提交人身份一律服务端按登录态解析，不接受客户端指定 userKey。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.response import paginate, success
from app.core.security import get_current_user, require_staff
from app.services import feedback_service as svc

router = APIRouter(prefix="/feedback", tags=["帮助与反馈"])


class FeedbackSubmit(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="反馈正文（≥5 字）")
    category: Optional[str] = Field("OTHER", description="BUG/SUGGESTION/CONSULT/COMPLAINT/OTHER")
    title: Optional[str] = Field(None, max_length=120)
    contact: Optional[str] = Field(None, max_length=100)


class FeedbackHandle(BaseModel):
    action: str = Field(..., description="ACCEPT / REPLY / CLOSE")
    reply: Optional[str] = Field(None, max_length=2000)


# ── 提交侧（本人）──

@router.post("", summary="提交反馈（本人；user_key 由登录态解析）")
def feedback_submit(body: FeedbackSubmit, user=Depends(get_current_user)):
    return success(svc.submit(body), message="已提交")


@router.get("/my", summary="我的反馈历史（本人）")
def feedback_my(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                user=Depends(get_current_user)):
    items, total = svc.my_list(page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ── 处理侧（学工/管理角色）──

@router.get("", summary="反馈工单列表（处理侧，按租户+状态/类型/关键词）")
def feedback_list(status: Optional[str] = None, category: Optional[str] = None,
                  keyword: Optional[str] = None, page: int = Query(1, ge=1),
                  pageSize: int = Query(20, ge=1, le=100), user=Depends(require_staff)):
    items, total = svc.list_all(status, category, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats", summary="反馈汇总（按状态计数）")
def feedback_stats(user=Depends(require_staff)):
    return success(svc.stats())


@router.get("/{feedbackId}", summary="反馈工单详情（处理侧）")
def feedback_detail(feedbackId: int = Path(...), user=Depends(require_staff)):
    return success(svc.get_one(feedbackId))


@router.post("/{feedbackId}/handle", summary="受理/回复/办结（处理侧，记受理人）")
def feedback_handle(body: FeedbackHandle, feedbackId: int = Path(...), user=Depends(require_staff)):
    return success(svc.handle(feedbackId, body.action, body.reply or ""), message="已处理")
