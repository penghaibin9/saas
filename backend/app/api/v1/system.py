"""系统信息接口。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.core.response import success

router = APIRouter()


@router.get("/system/info", summary="系统信息 / 能力开关")
def system_info():
    now = datetime.now(timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))).isoformat(timespec="seconds")
    return success({
        "appName": settings.APP_NAME,
        "env": settings.APP_ENV,
        "version": "0.1.0-skeleton",
        "apiPrefix": settings.API_V1_PREFIX,
        "tenancyMode": settings.TENANCY_MODE,
        "databaseConnected": settings.DB_ENABLED,   # 本阶段恒 False：未连真实库
        "serverTime": now,
        "capabilities": {
            "auth": "mock", "rbac": "mock", "tenantBrand": "mock",
            "todo": "mock", "message": "mock", "audit": "reserved",
            "fileUpload": "placeholder", "import": "placeholder",
            "export": "placeholder", "database": "reserved(not-connected)",
        },
    })
