"""D3-U 学籍异动便利性 Router。

新增统一提交 + 材料读取；legacy 五入口与 `/scheduled` 均继续保留兼容，
内部仍调用同一个 change_service.submit canonical。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.routers import status_change_router
from app.modules.academic_affairs.services import status_change_material_service as material_svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])


class StatusChangeConvenienceSubmit(status_change_router.StatusChangeSubmit):
    effectiveDate: Optional[str] = Field(
        None,
        description="可选 ISO-8601 计划生效时间；为空=终审通过立即生效",
    )
    materialFileIds: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="统一文件中心已上传且安全可用的 TEMP_PRIVATE fileId，最多 10 个",
    )


@router.post("/status-changes/convenience-submit", summary="D3-U：统一发起异动（立即/计划生效 + 正式材料）")
def status_change_convenience_submit(
    body: StatusChangeConvenienceSubmit,
    user=Depends(require_permission(status_change_router._SC_APPLY)),
):
    return success(
        material_svc.submit_with_materials(body, user, body.materialFileIds),
        message="异动已提交",
    )


@router.get("/status-changes/{changeId}/materials", summary="D3-U：读取学籍异动正式材料")
def status_change_materials(
    changeId: int = Path(...),
    user=Depends(status_change_router._SC_LIST_VIEW),
):
    return success({"items": material_svc.list_materials(changeId, user)})
