"""平台端沙箱恢复兼容入口。

同一路径保持历史合同：
- legacy-100 fixture / 开发沙箱：仍调用原 reset_sandbox()，旧测试与开发流程不变；
- standard-20k 售前沙箱：只恢复轻量销售故事线，保留 20K 背景数据。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.platform import require_platform_super_admin
from app.core.exceptions import AppException
from app.core.response import success
from app.services import audit_log

router = APIRouter(prefix="/platform", tags=["16·平台总控（仅平台超管）"])


@router.post("/tenants/{tenant_id}/reset-sandbox-data", summary="恢复演示沙箱（20K轻量故事线/旧沙箱兼容）")
def reset_sandbox_compat(tenant_id: int, user=Depends(require_platform_super_admin)):
    from app.db.session import db_enabled, get_sessionmaker
    from app.services.sandbox_service import SANDBOX_CODE, SANDBOX_TID, reset_sandbox
    from app.services.sandbox_school_story_reset import (is_standard_20k_sandbox,
                                                         restore_sales_storylines)

    if tenant_id != SANDBOX_TID:
        raise AppException("NO_PERMISSION", f"仅 {SANDBOX_CODE} 支持恢复演示数据")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "恢复演示沙箱需要启用真实数据库")

    db = get_sessionmaker()()
    try:
        if is_standard_20k_sandbox(db, SANDBOX_TID):
            story = restore_sales_storylines(db, SANDBOX_TID)
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
