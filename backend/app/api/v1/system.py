"""系统信息接口。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends

from app.core.config import settings
from app.core.response import success
from app.core.permissions import require_permission

router = APIRouter()


@router.get("/system/identity-import/role-templates", summary="师生导入可选的 SaaS 预设角色")
def identity_role_templates(user=Depends(require_permission("systemAdmin.user.view"))):
    from app.services.saas_role_templates import role_catalog
    return success(role_catalog(teacher_only=True))


@router.post("/system/identity-import/validate", summary="师生账号导入预检（不落库）")
def identity_import_validate(body: dict = Body(...),
                             user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_service import run_identity_import
    return success(run_identity_import(user, body, dry_run=True))


@router.post("/system/identity-import/confirm", summary="师生账号导入确认（唯一批量建号入口）")
def identity_import_confirm(body: dict = Body(...),
                            user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_service import run_identity_import
    return success(run_identity_import(user, body, dry_run=False))


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
