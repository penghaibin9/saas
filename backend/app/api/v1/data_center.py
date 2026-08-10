"""A4 / P0-06 数据驾驶舱服务端真值 API。"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.response import paginate, success
from app.core.security import require_staff
from app.services import data_center_service as svc

router = APIRouter(prefix="/data-center", tags=["data-center"])

# A4 当前只有 REGISTERED 的查询条件真正落到各域真实表。
# NATURAL 不能只换标签继续复用同一组数字，因此正式 API 暂不接受。
SupportedCaliber = Literal["REGISTERED"]


class ReportCreateBody(BaseModel):
    name: str
    category: str = "ACADEMIC"
    cycle: str = "MONTHLY"
    caliber: SupportedCaliber = "REGISTERED"
    scopeName: str = "全校"
    description: str = ""
    query: dict[str, Any] = Field(default_factory=dict)
    layout: dict[str, Any] = Field(default_factory=dict)


class ReportUpdateBody(BaseModel):
    version: int
    name: str | None = None
    category: str | None = None
    cycle: str | None = None
    caliber: SupportedCaliber | None = None
    scopeName: str | None = None
    description: str | None = None
    query: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None


class VersionBody(BaseModel):
    version: int


class VoidBody(VersionBody):
    reason: str


@router.get("/context", summary="驾驶舱真实角色/数据范围/品牌上下文")
def context(user=Depends(require_staff)):
    data = svc.get_context(user)
    # 服务端只广告真实可执行的统计口径；未实现 NATURAL 前禁止前端出现假切换。
    filters = data.get("filterOptions") if isinstance(data, dict) else None
    if isinstance(filters, dict):
        filters["calibers"] = [
            item for item in (filters.get("calibers") or [])
            if item.get("value") == "REGISTERED"
        ]
    return success(data)


@router.get("/reports", summary="专题报表列表（MySQL 真值）")
def reports(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    category: str | None = None,
    status: str | None = None,
    user=Depends(require_staff),
):
    items, total = svc.list_reports(
        user, page=page, page_size=pageSize, keyword=keyword, category=category, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/reports", summary="新建专题报表草稿")
def create_report(body: ReportCreateBody, user=Depends(require_staff)):
    return success(svc.create_report(user, body.model_dump()), message="报表草稿已创建")


@router.get("/reports/{report_id}", summary="专题报表详情/已发布冻结指标")
def report_detail(report_id: str, user=Depends(require_staff)):
    return success(svc.get_report_detail(user, report_id))


@router.put("/reports/{report_id}", summary="编辑专题报表工作副本（版本锁）")
def update_report(report_id: str, body: ReportUpdateBody, user=Depends(require_staff)):
    payload = body.model_dump(exclude_none=True)
    return success(svc.update_report(user, report_id, payload), message="报表配置已保存")


@router.post("/reports/{report_id}/publish", summary="发布专题报表并冻结指标版本")
def publish_report(report_id: str, body: VersionBody, user=Depends(require_staff)):
    return success(svc.publish_report(user, report_id, body.model_dump()), message="报表已发布")


@router.post("/reports/{report_id}/withdraw", summary="撤回已发布专题报表")
def withdraw_report(report_id: str, body: VersionBody, user=Depends(require_staff)):
    return success(svc.withdraw_report(user, report_id, body.model_dump()), message="报表已撤回")


@router.post("/reports/{report_id}/void", summary="作废专题报表（留痕，不物理删除）")
def void_report(report_id: str, body: VoidBody, user=Depends(require_staff)):
    return success(svc.void_report(user, report_id, body.model_dump()), message="报表已作废")


@router.get("/reports/{report_id}/versions", summary="专题报表发布版本历史")
def versions(report_id: str, user=Depends(require_staff)):
    return success({"items": svc.list_versions(user, report_id)})


@router.get("/audit-logs", summary="数据驾驶舱报表真实审计")
def audit_logs(
    targetId: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_staff),
):
    return success(svc.list_audits(user, report_id=targetId, limit=limit))
