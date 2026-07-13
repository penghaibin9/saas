"""Staff endpoints for formal internship application review."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.internship.services import internship_application_service as svc
from app.services import audit_log

router = APIRouter(prefix="/internship/applications", tags=["岗位实习-正式申请"])


@router.get("")
def applications(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                 status: Optional[str] = None, applicationType: Optional[str] = None,
                 keyword: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_applications(page, pageSize, status, applicationType, keyword, user)
    return success(paginate(items, total, page, pageSize))


@router.get("/{application_id}")
def application_detail(application_id: str, user=Depends(get_current_user)):
    return success(svc.get_application(application_id, user))


@router.post("/{application_id}/review")
def application_review(application_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = svc.review_application(application_id, (body or {}).get("action", ""),
                                    (body or {}).get("comment", ""), user)
    audit_log.record("审核实习申请", f"internship-application:{application_id}",
                     detail={"action": (body or {}).get("action", "")})
    return success(result, message="申请已处理")
