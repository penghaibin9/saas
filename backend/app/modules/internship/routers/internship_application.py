"""Staff endpoints for formal internship application review.

权限（P3）：查询 internship.application.view，审核 internship.application.review
（校管/学院负责人/指导教师均可，数据范围由 service 收敛）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_application_service as svc
from app.services import audit_log

router = APIRouter(prefix="/internship/applications", tags=["岗位实习-正式申请"])

_P_VIEW = "internship.application.view"
_P_REVIEW = "internship.application.review"


@router.get("")
def applications(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                 status: Optional[str] = None, applicationType: Optional[str] = None,
                 keyword: Optional[str] = None, user=Depends(require_permission(_P_VIEW))):
    items, total = svc.list_applications(page, pageSize, status, applicationType, keyword, user)
    return success(paginate(items, total, page, pageSize))


@router.get("/{application_id}")
def application_detail(application_id: str, user=Depends(require_permission(_P_VIEW))):
    return success(svc.get_application(application_id, user))


@router.post("/{application_id}/review")
def application_review(application_id: str, body: dict = Body(...), user=Depends(require_permission(_P_REVIEW))):
    result = svc.review_application(application_id, (body or {}).get("action", ""),
                                    (body or {}).get("comment", ""), user)
    audit_log.record("审核实习申请", f"internship-application:{application_id}",
                     detail={"action": (body or {}).get("action", "")})
    return success(result, message="申请已处理")
