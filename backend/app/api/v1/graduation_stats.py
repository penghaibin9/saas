"""毕业设计中心 · 毕设统计 API（/api/v1/graduation/gd-stats/*）。只读聚合，不改动业务表。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.services import graduation_stats_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-毕设统计"])


@router.get("/gd-stats/overview", summary="毕设总览统计（跨模块聚合）")
def gd_stats_overview(user=Depends(get_current_user)):
    return success(svc.overview_stats())


@router.get("/gd-stats/college-comparison", summary="学院/专业对比统计")
def gd_stats_college_comparison(user=Depends(get_current_user)):
    return success(svc.college_comparison())
