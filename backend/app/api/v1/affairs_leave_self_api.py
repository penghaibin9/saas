"""学生本人请假专用入口。

学生 PC 与小程序只做渠道适配，底层统一调用 affairs_leave_service.apply_leave。
客户端不得提交 studentId，学生身份由当前登录账号在服务端解析。
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.exceptions import AppException
from app.core.response import success
from app.core.security import get_current_user
from app.services import affairs_leave_service as leave_svc
from app.services.db_service import session
from app.services.mobile_student_service import _require_student, resolve_student
from app.services.affairs_leave_date_contract import normalize_range

router = APIRouter(tags=["学工中心-学生本人请假"])

_ALLOWED_TYPES = {"SICK", "PERSONAL", "HOME", "HOSPITAL", "GOOUT", "OTHER"}


class StudentLeaveApplyBody(BaseModel):
    leaveType: str = Field("PERSONAL", max_length=30)
    startTime: str = Field(..., min_length=10, max_length=30)
    endTime: str = Field(..., min_length=10, max_length=30)
    reason: str = Field(..., min_length=5, max_length=300)
    # 上传阶段只产生 TEMP_PRIVATE 文件；请假命令在同一事务中完成正式绑定。
    fileIds: list[str] = Field(default_factory=list, max_length=3)


def _apply_for_current_student(body: StudentLeaveApplyBody, user: dict) -> dict:
    current = _require_student(user)
    leave_type = str(body.leaveType or "PERSONAL").strip().upper()
    if leave_type not in _ALLOWED_TYPES:
        raise AppException("VALIDATION_ERROR", "请假类型不正确")

    normalize_range(body.startTime, body.endTime)

    with session() as db:
        student = resolve_student(db, current)
        if not student:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        student_id = int(student.id)

    command = SimpleNamespace(
        studentId=str(student_id),
        leaveType=leave_type,
        startTime=body.startTime,
        endTime=body.endTime,
        reason=body.reason.strip(),
        fileIds=list(body.fileIds or []),
    )
    return leave_svc.apply_leave(command, current, skip_scope_check=True)


@router.post("/portal/affairs/leave", summary="学生 PC 发起请假（本人）")
def portal_leave_apply(body: StudentLeaveApplyBody, user=Depends(get_current_user)):
    return success(_apply_for_current_student(body, user), message="请假已提交")


@router.post("/mobile/affairs/leave", summary="学生小程序发起请假（本人）")
def mobile_leave_apply(body: StudentLeaveApplyBody, user=Depends(get_current_user)):
    return success(_apply_for_current_student(body, user), message="请假已提交")


@router.get("/portal/affairs/leave/{leave_id}", summary="学生 PC 查看本人请假办理详情")
@router.get("/mobile/affairs/leave/{leave_id}/detail", summary="学生小程序查看本人请假办理详情")
def self_leave_detail(leave_id: int, user=Depends(get_current_user)):
    from app.services.mobile_affairs_service import leave_detail_my
    return success(leave_detail_my(user, leave_id))
