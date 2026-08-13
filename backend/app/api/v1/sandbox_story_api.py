"""平台端沙箱恢复兼容入口。

同一路径保持历史合同：
- legacy-100 fixture / 开发沙箱：仍调用原 reset_sandbox()，旧测试与开发流程不变；
- standard-20k 售前沙箱：只恢复轻量销售故事线，保留 20K 背景数据。

本模块会在 route_registration 开始前，把 platform.router 中历史同路径 APIRoute 原位替换。
这是为了兼容项目现有循环导入：应用可能在 router.py 的尾部补充路由逻辑之前就复制主 Router，
因此 canonical 平台 Router 必须从一开始就是正确语义，不能依赖“注册后再删除旧路由”。
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

    if tenant_id != SANDBOX_TID:
        raise AppException("NO_PERMISSION", f"仅 {SANDBOX_CODE} 支持恢复演示数据")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "恢复演示沙箱需要启用真实数据库")

    db = get_sessionmaker()()
    try:
        if story_svc.is_standard_20k_sandbox(db, SANDBOX_TID):
            story = story_svc.restore_sales_storylines(db, SANDBOX_TID)
            out = {
                "tenant": SANDBOX_CODE,
                "tenantId": str(SANDBOX_TID),
                "dryRun": False,
                "reseeded": story,
            }
            message = "20K 背景数据已保留，销售演示故事线已恢复"
            action = "PLATFORM_SANDBOX_STORY_RESET"
        else:
            out = reset_sandbox(db, dry_run=False)
            message = "开发沙箱已按 legacy-100 基线恢复"
            action = "PLATFORM_SANDBOX_LEGACY_RESET"
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
    """把历史平台恢复路由原位替换为唯一的兼容路由，幂等且不改变其它平台路由顺序。"""
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


# 必须在 register_all_routes() 之前执行；router.py 会显式提前导入本模块。
install_into_platform_router()
