"""岗位实习中心 · 实习保险核验 API（/api/v1/internship/insurances/*）。

学生端提交保单(mobile) → 教师/管理端核验(通过/驳回)。数据范围与状态机由 service 处理。
PC 管理端（学生 403 由注册处 require_staff 统一门禁）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.internship.services import internship_insurance_service as svc

router = APIRouter(prefix="/internship", tags=["岗位实习-实习保险"])


@router.get("/insurances", summary="实习保险列表（教师/管理端，按数据范围）")
def insurance_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   status: Optional[str] = None, keyword: Optional[str] = None,
                   user=Depends(get_current_user)):
    items, total = svc.list_insurances(page, pageSize, status=status, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/insurances/{insurance_id}/verify", summary="核验实习保险（APPROVE/REJECT）")
def insurance_verify(insurance_id: int, body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    return success(svc.verify_insurance(insurance_id, b.get("action", ""), b.get("comment", ""), user=user))
