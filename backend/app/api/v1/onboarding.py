"""新学校开局向导 API（/api/v1/onboarding/*）。
- POST /onboarding/tenant   创建新租户（平台运营）
- POST /onboarding/validate 开局数据 dry-run 校验（不落库，返回行号错误 + 预演统计）
- POST /onboarding/confirm  开局数据落库（一个事务；atomic 下有错整批回滚）
仅平台运营/学校管理员可用；学生/教师 403；严格禁止跨租户写入。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.services import school_onboarding_service as onb

router = APIRouter(prefix="/onboarding", tags=["新学校开局向导"])


@router.post("/tenant", summary="创建新租户（平台运营）")
def create_tenant(body: dict = Body(...), user=Depends(get_current_user)):
    return success(onb.create_tenant_step(user, body))


@router.post("/validate", summary="开局数据校验（dry-run，不落库）")
def validate(body: dict = Body(...), user=Depends(get_current_user)):
    return success(onb.run_onboarding(user, body, dry_run=True))


@router.post("/confirm", summary="开局数据落库（事务；atomic 下有错整批回滚）")
def confirm(body: dict = Body(...), user=Depends(get_current_user)):
    return success(onb.run_onboarding(user, body, dry_run=False))
