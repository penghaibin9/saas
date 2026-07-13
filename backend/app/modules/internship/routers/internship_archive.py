"""岗位实习中心 · 实习归档 API（/api/v1/internship/archive/*）。

材料完整度/缺失 → 归档(force) → 生成归档包(zip) → 撤销 → 企业/批次聚合 → 导出。
数据范围与角色越权由 service 内 _scope_ctx/in_scope 处理；PC 管理端（学生 403 由注册处 require_staff 统一门禁）。
静态子路由（by-enterprise/by-batch/export）声明在 /archive/{internship_id} 之前，避免被路径参数吞掉。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.internship.services import internship_archive_service as svc

router = APIRouter(prefix="/internship", tags=["岗位实习-实习归档"])


@router.get("/archive", summary="归档台账列表（材料完整度/缺失，按数据范围）")
def archive_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                 keyword: Optional[str] = None, batchId: Optional[str] = None,
                 onlyIncomplete: bool = False, user=Depends(get_current_user)):
    items, total = svc.list_by_student(page, pageSize, keyword=keyword, batch_id=batchId,
                                       only_incomplete=onlyIncomplete, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/archive/by-enterprise", summary="按企业聚合归档完整度")
def archive_by_enterprise(user=Depends(get_current_user)):
    return success(svc.by_enterprise(user=user))


@router.get("/archive/by-batch", summary="按批次聚合归档完整度")
def archive_by_batch(user=Depends(get_current_user)):
    return success(svc.by_batch(user=user))


@router.post("/archive/export", summary="导出归档台账（xlsx）")
def archive_export(keyword: Optional[str] = None, batchId: Optional[str] = None,
                   user=Depends(get_current_user)):
    return success(svc.export_archives(user=user, keyword=keyword, batch_id=batchId))


@router.get("/archive/{internship_id}", summary="归档详情（材料标签/审计留痕）")
def archive_detail(internship_id: int, user=Depends(get_current_user)):
    return success(svc.get_archive(internship_id, user=user))


@router.post("/archive/{internship_id}/archive", summary="归档学生（完整→直接；缺失需 force）")
def archive_do(internship_id: int, body: Optional[dict] = Body(None), user=Depends(get_current_user)):
    force = bool((body or {}).get("force", False))
    return success(svc.archive_student(user, internship_id, force=force))


@router.post("/archive/{internship_id}/package", summary="生成归档包（zip，落文件中心）")
def archive_package(internship_id: int, user=Depends(get_current_user)):
    return success(svc.build_package(user, internship_id))


@router.post("/archive/{internship_id}/revoke", summary="撤销归档（需原因，≥5 字）")
def archive_revoke(internship_id: int, body: Optional[dict] = Body(None), user=Depends(get_current_user)):
    reason = (body or {}).get("reason", "")
    return success(svc.revoke_archive(user, internship_id, reason=reason))
