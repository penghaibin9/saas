"""V2-04 成绩身份写入口。

替换旧总路由中只接收 courseName 的三个端点：
- 补考纳入必须从候选成绩选择 gradeId；
- 重修报名必须从学生本人当前有效挂科成绩选择 gradeId；
- 免修申请必须选择课程库具体 courseId。
URL与权限保持不变。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.response import success
from app.core.security import get_current_user
from app.core.permissions import require_permission
from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup_service

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-成绩身份"])


def _student_only(user: dict = Depends(get_current_user)) -> dict:
    if str(user.get("userType") or "").upper() != "STUDENT":
        raise AppException("NO_PERMISSION", "仅学生本人可提交该申请", http_status=403)
    return user


class MakeupIdentityEnrollBody(BaseModel):
    gradeId: int = Field(..., gt=0, description="补考候选中的原失败正式成绩ID")
    acadStudentId: int = Field(..., gt=0)
    originScore: Optional[int] = Field(default=None, ge=0, le=100)


class RetakeIdentityApplyBody(BaseModel):
    gradeId: int = Field(..., gt=0, description="学生本人当前有效挂科成绩ID")
    termCode: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=500)


class ExemptionIdentityApplyBody(BaseModel):
    courseId: int = Field(..., gt=0, description="课程库具体版本ID")
    termCode: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=500)
    materialFileIds: list[int] = Field(default_factory=list)


@router.post("/makeup/batches/{batch_id}/enroll", summary="按原失败成绩纳入补考名单")
def makeup_identity_enroll(
    body: MakeupIdentityEnrollBody,
    batch_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.makeup.manage")),
):
    return success(
        makeup_service.enroll_makeup_by_grade(
            user,
            batch_id,
            body.gradeId,
            body.acadStudentId,
            body.originScore,
        ),
        message="已纳入",
    )


@router.post("/retake/apply", summary="按本人挂科成绩提交重修报名")
def retake_identity_apply(body: RetakeIdentityApplyBody, user=Depends(_student_only)):
    return success(makeup_service.retake_apply(user, body), message="重修报名已提交")


@router.post("/exemption/apply", summary="按课程库具体版本提交免修申请")
def exemption_identity_apply(body: ExemptionIdentityApplyBody, user=Depends(_student_only)):
    return success(makeup_service.exemption_apply(user, body), message="免修申请已提交")
