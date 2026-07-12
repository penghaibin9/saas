"""毕业设计中心 · 指导过程记录 API（/api/v1/graduation/gd-guidances/*）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_guidance import GuidanceCreate, GuidanceVoidRequest
from app.services import audit_log
from app.modules.graduation.services import graduation_guidance_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-指导过程"])


@router.get("/gd-guidances/stats", summary="指导频次统计（GD-R06 指导不足预警口径）")
def gd_guidance_stats(threshold: int = Query(3, ge=1, le=50), user=Depends(get_current_user)):
    return success(svc.guidance_stats(threshold))


@router.get("/gd-guidances", summary="指导记录列表（按学生/关键词筛选）")
def gd_guidances(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                 gdStudentId: Optional[str] = None, keyword: Optional[str] = None,
                 user=Depends(get_current_user)):
    items, total = svc.list_guidance(page, pageSize, gd_student_id=gdStudentId, keyword=keyword)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-guidances/{gd_student_id}", summary="新增指导记录")
def gd_guidance_create(gd_student_id: str, body: GuidanceCreate, user=Depends(get_current_user)):
    result = svc.create_guidance(gd_student_id, body.model_dump())
    audit_log.record("新增指导记录", f"graduation-guidance:{result['id']}")
    return success(result, message="已记录")


@router.post("/gd-guidances/records/{gid}/void", summary="撤销指导记录（原因≥5字）")
def gd_guidance_void(gid: str, body: GuidanceVoidRequest, user=Depends(get_current_user)):
    result = svc.void_guidance(gid, body.reason)
    audit_log.record("撤销指导记录", f"graduation-guidance:{gid}", detail={"reason": body.reason})
    return success(result, message="已撤销")
