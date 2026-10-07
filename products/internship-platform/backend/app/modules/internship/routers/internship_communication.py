"""岗位实习中心 · 企业沟通记录 API（/api/v1/internship/communications/*，07 §5.1）。

权限（P3/P4）：查询 internship.communication.view，新建/作废/后续 internship.communication.manage
（指导教师对本人指导学生相关沟通可操作，数据范围由 service scope 收敛）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_communication_service as svc

router = APIRouter(prefix="/internship/communications", tags=["岗位实习-企业沟通"])

_P_VIEW = "internship.communication.view"
_P_MANAGE = "internship.communication.manage"


@router.get("", summary="企业沟通记录列表（按批次 + 数据范围）")
def communications(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   batchId: Optional[str] = Query(None, description="实习批次（必填）"),
                   enterpriseId: Optional[str] = None, studentId: Optional[str] = None,
                   status: Optional[str] = None, user=Depends(require_permission(_P_VIEW))):
    items, total = svc.list_communications(
        page, pageSize, enterprise_id=enterpriseId, student_id=studentId, status=status,
        batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/{comm_id}", summary="企业沟通详情（含审计留痕）")
def communication_detail(comm_id: int, user=Depends(require_permission(_P_VIEW))):
    return success(svc.get_communication(comm_id, user=user))


@router.post("", summary="新建企业沟通记录")
def create_communication(body: dict = Body(...), user=Depends(require_permission(_P_MANAGE))):
    return success(svc.create_communication(body, user=user), message="已记录")


@router.post("/{comm_id}/void", summary="作废沟通记录（需原因≥2字）")
def void_communication(comm_id: int, body: dict = Body(default=None), user=Depends(require_permission(_P_MANAGE))):
    return success(svc.void_communication(comm_id, (body or {}).get("reason", ""), user=user), message="已作废")


@router.post("/{comm_id}/follow-up-done", summary="完成后续事项")
def follow_up_done(comm_id: int, user=Depends(require_permission(_P_MANAGE))):
    return success(svc.complete_follow_up(comm_id, user=user), message="已完成")
