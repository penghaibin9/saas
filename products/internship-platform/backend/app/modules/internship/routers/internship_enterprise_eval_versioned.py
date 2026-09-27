"""企业评价版本化审核端点。

旧 `/enterprise-evals/{id}/review` 历史路由未透传 expectedVersion；Service 已默认拒绝
缺版本请求。本端点供当前管理 PC 使用，避免任何审核静默覆盖。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import internship_enterprise_eval_service as service
from app.services import audit_log

router = APIRouter(prefix="/internship/enterprise-evals", tags=["岗位实习-企业评价版本化审核"])


@router.post("/{eval_id}/review-versioned", summary="按当前版本独立审核企业评价")
def review_versioned(
    eval_id: str,
    body: dict = Body(...),
    user=Depends(require_permission("internship.eval.enterprise.review")),
):
    payload = body or {}
    result = service.review(
        user,
        eval_id,
        str(payload.get("action") or "").upper(),
        payload.get("comment") or "",
        expected_version=payload.get("expectedVersion", payload.get("version")),
    )
    audit_log.record(
        "审核企业评价",
        f"internship-enterprise-eval:{eval_id}",
        detail={"action": payload.get("action"), "newVersion": result.get("version")},
    )
    return success(result, message="审核完成")
