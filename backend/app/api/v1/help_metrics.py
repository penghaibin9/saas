"""Help Center V3-08 质量与自助服务指标 API。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.permissions import enforce_permission
from app.core.response import success
from app.core.security import get_current_user
from app.services import help_metrics_service as svc

router = APIRouter(prefix="/help/metrics", tags=["Help Center · 质量指标"])


class HelpMetricEvent(BaseModel):
    eventType: Literal["SEARCH", "ARTICLE_VIEW", "HELPFUL", "NOT_HELPFUL"]
    articleId: str | None = Field(default=None, max_length=100)
    query: str | None = Field(default=None, max_length=200)
    resultCount: int | None = Field(default=None, ge=0, le=1000)
    source: str | None = Field(default=None, max_length=40)
    category: str | None = Field(default=None, max_length=80)
    roleGroup: str | None = Field(default=None, max_length=60)


@router.post("/events", summary="记录帮助搜索/阅读/解决反馈（不保存搜索原文）")
def record_help_metric(body: HelpMetricEvent, user=Depends(get_current_user)):
    return success(svc.record_event(
        event_type=body.eventType,
        article_id=body.articleId or "",
        query=body.query or "",
        result_count=body.resultCount,
        source=body.source or "",
        category=body.category or "",
        role_group=body.roleGroup or "",
    ))


@router.get("/summary", summary="近 N 天 Help Center 质量/自助服务指标")
def help_metric_summary(
    days: int = Query(default=30, ge=1, le=90),
    user=Depends(get_current_user),
):
    # 真实汇总属于学校级运营/审计数据，不因为帮助页本身可读就向普通用户开放。
    enforce_permission(user, "systemAdmin.audit.view")
    return success(svc.summary(window_days=days))
