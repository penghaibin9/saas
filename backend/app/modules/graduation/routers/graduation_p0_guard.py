"""Exact high-risk routes registered before legacy graduation routers."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.exceptions import AppException
from app.core.response import success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_guidance import GuidanceVoidRequest
from app.modules.graduation.schemas.graduation_student import GdStudentGradQualRequest
from app.modules.graduation.services import graduation_p0_service as p0

router = APIRouter(prefix="/graduation", tags=["毕业设计-P0安全门"])


@router.post("/gd-guidances/records/{gid}/void", summary="撤销指导记录（范围锁定）")
def gd_guidance_void(gid: str, body: GuidanceVoidRequest, user=Depends(get_current_user)):
    if len((body.reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "撤销原因必填且不少于 5 字")
    return success(p0.void_guidance_scoped(gid, body.reason), message="已撤销")


@router.post("/gd-students/{record_id}/grad-qual", summary="毕业资格联动状态（已废弃，只读镜像）")
def student_grad_qual(
    record_id: str,
    body: GdStudentGradQualRequest,
    user=Depends(get_current_user),
):
    raise AppException(
        "DATA_CONFLICT",
        "毕业设计中心不再直接裁决最终毕业资格。请完成毕设成绩与归档，由教务中心统一重算毕业资格。",
    )
