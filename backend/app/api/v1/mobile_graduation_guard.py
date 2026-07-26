"""High-risk graduation mobile overrides.

Registered before the legacy aggregate mobile router. Exact path matches use the
same evidence-backed confirmation flow as the student PC portal instead of the
old status-only confirmation endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.modules.graduation.services.graduation_taskbook_confirmation_service import (
    confirm_with_evidence,
)

router = APIRouter(prefix="/mobile/graduation", tags=["移动端聚合-毕业设计高风险修复"])


@router.post("/taskbook/confirm", summary="任务书·本人确认（内容哈希+版本证据）")
def graduation_taskbook_confirm_evidence(
    body: dict = Body(default={}),
    user=Depends(get_current_user),
):
    payload = dict(body or {})
    return success(confirm_with_evidence(
        user,
        expected_version=payload.get("taskbookVersion") or payload.get("expectedVersion"),
        confirm=True,
    ), message="已确认")
