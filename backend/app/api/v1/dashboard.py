"""仪表盘概览。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.services import mock_dashboard_service as dash_svc

router = APIRouter()


@router.get("/summary", summary="工作台概览（按当前身份 + 数据范围裁剪）")
def summary(user=Depends(get_current_user)):
    return success(dash_svc.get_summary(user))


@router.get("/lifecycle-overview", summary="生命周期总览（六阶段人数分布，按数据范围裁剪）")
def lifecycle_overview(user=Depends(get_current_user)):
    return success(dash_svc.get_lifecycle_overview(user))
