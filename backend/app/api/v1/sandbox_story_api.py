"""平台端沙箱恢复兼容入口。

同一路径保持历史合同：
- legacy-100 fixture / 开发沙箱：仍调用原 reset_sandbox()，旧测试与开发流程不变；
- standard-20k 售前沙箱：只恢复轻量销售故事线，保留 20K 背景数据；
- standard-20k-damaged：拒绝降级，必须走维护级修复/全量重建。

本模块会在 route_registration 开始前，把 platform.router 中历史同路径 APIRoute 原位替换。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute

from app.api.v1 import platform as platform_api
from app.core.exceptions import AppException
from app.core.response import success
from app.services import audit_log

router = APIRouter(prefix="/platform", tags=["16·平台总控（仅平台超管）"])


@router.post("/tenants/{tenant_id}/reset-sandbox-data", summary="恢复演示沙箱（20K轻量故事线/旧沙箱兼容）")
def reset_sandbox_compat(tenant_id: int, user=Depends(platform_api.require_platform_super_admin)):
    from app.db.session import db_enabled, get_sessionmaker
    from app.services.sandbox_service import SANDBOX_CODE, SANDBOX_TID, reset_sandbox
    from app.services import sandbox_school_story_reset as story_svc
    from app.services.sandbox_school_profile import (
        PROFILE_LEGACY,
        PROFILE_STANDARD,
        PROFILE_STANDARD_DAMAGED,
        classify_sandbox_profile,
    )

    if tenant_id != SANDBOX_TID:
        raise AppException("NO_PERMISSION", f"仅 {SANDBOX_CODE} 支持恢复演示数据")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "恢复演示沙箱需要启用真实数据库")

    db = get_sessionmaker()()
    try:
        profile = classify_sandbox_profile(db, SANDBOX_TID)
        mode = profile["profile"]
        if mode == PROFILE_STANDARD:
            story = story_svc.restore_sales_storylines(db, SANDBOX_TID)
            out = {
                "tenant": SANDBOX_CODE,
                "tenantId": str(SANDBOX_TID),
                "dryRun": False,
                "profile": profile,
                "reseeded": story,
            }
            message = "20K 背景数据已保留，销售演示故事线已恢复"
            action = "PLATFORM_SANDBOX_STORY_RESET"
        elif mode == PROFILE_STANDARD_DAMAGED:
            raise AppException(
                "DATA_CONFLICT",
                "检测到受损的 standard-20k 试点沙箱，已阻断 legacy-100 降级恢复；"
                "请使用维护级 standard-20k 重建/修复流程。",
                data=profile,
            )
        elif mode == PROFILE_LEGACY:
            out = reset_sandbox(db, dry_run=False)
            out["profileBeforeReset"] = profile
            message = "开发沙箱已按 legacy-100 基线恢复"
            action = "PLATFORM_SANDBOX_LEGACY_RESET"
        else:
            raise AppException(
                "DATA_CONFLICT",
                "当前 sandbox 数据形态无法安全识别，已拒绝自动恢复，避免误删试点数据。",
                data=profile,
            )
    finally:
        db.close()

    audit_log.record(
        action,
        str(tenant_id),
        detail={"mode": out.get("reseeded", {}).get("mode", "legacy-100")},
        result="SUCCESS",
        tenant_id=tenant_id,
    )
    return success(out, message=message)


_RESET_SANDBOX_PATH = "/platform/tenants/{tenant_id}/reset-sandbox-data"


def install_into_platform_router() -> None:
    """把历史平台恢复路由原位替换为唯一兼容路由，幂等且不改变其它平台路由顺序。"""
    replacement = next(
        route for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == _RESET_SANDBOX_PATH
        and "POST" in (route.methods or set())
    )
    rebuilt = []
    inserted = False
    for route in platform_api.router.routes:
        is_target = (
            isinstance(route, APIRoute)
            and route.path == _RESET_SANDBOX_PATH
            and "POST" in (route.methods or set())
        )
        if not is_target:
            rebuilt.append(route)
            continue
        if not inserted:
            rebuilt.append(replacement)
            inserted = True
    if not inserted:
        rebuilt.append(replacement)
    platform_api.router.routes[:] = rebuilt


install_into_platform_router()
