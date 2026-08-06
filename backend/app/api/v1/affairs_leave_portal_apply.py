"""学生 PC 门户首次请假提交端点。

学生页面调用 POST /api/v1/portal/affairs/leave。该动作必须强制使用登录学生
本人档案，禁止客户端指定 studentId；正式状态机、受理人分配、待办和审计统一
复用 affairs_leave_service.apply_leave。
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Body, Depends

from app.core.exceptions import AppException
from app.core.response import success
from app.core.security import get_current_user
from app.services import affairs_leave_service as leave_svc
from app.student_portal.services.affairs_service import _resolve_self_id

router = APIRouter(prefix="/portal", tags=["学生PC门户"])

_ALLOWED_LEAVE_TYPES = {"SICK", "PERSONAL", "HOME", "HOSPITAL", "GOOUT", "OTHER"}


@router.post("/affairs/leave", summary="本人发起请假")
def affairs_leave_apply(body: dict = Body(...), user=Depends(get_current_user)):
    payload = body or {}
    leave_type = str(payload.get("leaveType") or "PERSONAL").strip().upper()
    start_time = str(payload.get("startTime") or "").strip()
    end_time = str(payload.get("endTime") or "").strip()
    reason = str(payload.get("reason") or "").strip()

    if leave_type not in _ALLOWED_LEAVE_TYPES:
        raise AppException("VALIDATION_ERROR", "不支持的请假类型")
    if not start_time or not end_time:
        raise AppException("VALIDATION_ERROR", "请填写请假开始和结束时间")
    if len(reason) < 5 or len(reason) > 300:
        raise AppException("VALIDATION_ERROR", "请假事由须为 5-300 字")

    student_id = _resolve_self_id(user)
    request_body = SimpleNamespace(
        studentId=str(student_id),
        leaveType=leave_type,
        startTime=start_time,
        endTime=end_time,
        reason=reason,
    )
    result = leave_svc.apply_leave(request_body, user, skip_scope_check=True)
    return success(result, message="请假已提交，等待辅导员审批")
