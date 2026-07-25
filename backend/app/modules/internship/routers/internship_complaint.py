"""岗位实习中心 · 企业投诉受理 API（/api/v1/internship/complaints/*，07 §5.3）。

权限（P4）：查询 internship.complaint.view（含督导只读、领导脱敏聚合）；
登记/受理/调查/办结/转风险/回访 internship.complaint.intake；
投诉人联系方式明文需 internship.complaint.sensitive（service 内按角色脱敏，领导 *.view 不含该码）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_complaint_service as svc

router = APIRouter(prefix="/internship/complaints", tags=["岗位实习-企业投诉"])

_P_VIEW = "internship.complaint.view"
_P_INTAKE = "internship.complaint.intake"


@router.get("", summary="企业投诉列表（按批次；联系方式按权限脱敏）")
def complaints(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               batchId: Optional[str] = Query(None, description="实习批次（必填）"),
               status: Optional[str] = None, enterpriseId: Optional[str] = None,
               severity: Optional[str] = None, user=Depends(require_permission(_P_VIEW))):
    items, total = svc.list_complaints(
        page, pageSize, status=status, enterprise_id=enterpriseId, severity=severity,
        batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/{complaint_id}", summary="投诉详情（含审计留痕，联系方式按权限脱敏）")
def complaint_detail(complaint_id: int, user=Depends(require_permission(_P_VIEW))):
    return success(svc.get_complaint(complaint_id, user=user))


@router.post("", summary="登记企业投诉（RECEIVED）")
def create_complaint(body: dict = Body(...), user=Depends(require_permission(_P_INTAKE))):
    return success(svc.create_complaint(body, user=user), message="已登记")


@router.post("/{complaint_id}/transition", summary="投诉状态迁移（ACCEPT/INVESTIGATE/RESOLVE/REJECT/WITHDRAW/CLOSE）")
def transition(complaint_id: int, body: dict = Body(...), user=Depends(require_permission(_P_INTAKE))):
    return success(svc.transition(complaint_id, (body or {}).get("action", ""), body, user=user), message="已更新")


@router.post("/{complaint_id}/to-risk", summary="投诉转风险单（保留双向链接）")
def to_risk(complaint_id: int, user=Depends(require_permission(_P_INTAKE))):
    return success(svc.to_risk(complaint_id, user=user), message="已转风险单")


@router.post("/{complaint_id}/followup", summary="投诉回访（办结/关闭后）")
def followup(complaint_id: int, body: dict = Body(default=None), user=Depends(require_permission(_P_INTAKE))):
    return success(svc.followup(complaint_id, (body or {}).get("result", ""), user=user), message="已回访")
