"""岗位实习中心 · 巡访计划 API（/api/v1/internship/visit-plans/*，07 §5.2）。

权限（P4）：查询 internship.visit.plan.view，创建/编辑/状态迁移 internship.visit.plan.manage
（指导教师处理分派给本人的计划，数据范围由 service owner scope 收敛）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_visit_plan_service as svc

router = APIRouter(prefix="/internship/visit-plans", tags=["岗位实习-巡访计划"])

_P_VIEW = "internship.visit.plan.view"
_P_MANAGE = "internship.visit.plan.manage"


@router.get("", summary="巡访计划列表（按数据范围）")
def visit_plans(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                status: Optional[str] = None, batchId: Optional[str] = None,
                user=Depends(require_permission(_P_VIEW))):
    items, total = svc.list_visit_plans(page, pageSize, status=status, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/{plan_id}", summary="巡访计划详情（含审计留痕）")
def visit_plan_detail(plan_id: int, user=Depends(require_permission(_P_VIEW))):
    return success(svc.get_visit_plan(plan_id, user=user))


@router.post("", summary="新建巡访计划（草稿）")
def create_visit_plan(body: dict = Body(...), user=Depends(require_permission(_P_MANAGE))):
    return success(svc.create_visit_plan(body, user=user), message="已创建")


@router.put("/{plan_id}", summary="编辑巡访计划（草稿/已发布可编辑）")
def update_visit_plan(plan_id: int, body: dict = Body(...), user=Depends(require_permission(_P_MANAGE))):
    return success(svc.update_visit_plan(plan_id, body, user=user), message="已保存")


@router.post("/{plan_id}/transition", summary="巡访计划状态迁移（PUBLISH/START/COMPLETE/CANCEL）")
def transition(plan_id: int, body: dict = Body(...), user=Depends(require_permission(_P_MANAGE))):
    return success(svc.transition(plan_id, (body or {}).get("action", ""), body, user=user), message="已更新")
