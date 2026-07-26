"""教师移动端超期销假批次化权威接口。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_module, require_permission
from app.core.response import success
from app.modules.internship.services import internship_student_leave_context_service as leaves

router = APIRouter(
    prefix="/mobile/teacher/internship/context",
    tags=["教师移动端-实习请假版本化"],
    dependencies=[Depends(require_module("internship"))],
)


@router.get("/leaves/overdue", summary="教师当前批次超期或已销假待办结记录")
def teacher_overdue_leaves(
    batchId: str = Query(..., min_length=1),
    user=Depends(require_permission("internship.leave.view")),
):
    return success(leaves.list_teacher_overdue(batchId, user))


@router.post("/leaves/{leave_id}/ack-return", summary="教师按版本确认销假办结并关闭关联风险")
def teacher_ack_leave_return(
    leave_id: str,
    body: dict = Body(...),
    user=Depends(require_permission("internship.leave.review")),
):
    return success(
        leaves.ack_overdue_return(user, leave_id, body or {}),
        message="销假已办结",
    )
