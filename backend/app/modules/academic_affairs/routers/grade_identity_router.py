"""V2-04 成绩身份写入口。

替换旧总路由中会丢失稳定身份的端点，URL与权限保持不变。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field, model_validator

from app.core.exceptions import AppException
from app.core.permissions import require_permission
from app.core.response import success
from app.core.security import get_current_user
from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_service
from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup_service

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-成绩身份"])


def _student_only(user: dict = Depends(get_current_user)) -> dict:
    if str(user.get("userType") or "").upper() != "STUDENT":
        raise AppException("NO_PERMISSION", "仅学生本人可提交该申请", http_status=403)
    return user


class GradeTaskIdentityCreateBody(BaseModel):
    teachingTaskId: Optional[int] = Field(default=None, gt=0)
    termId: Optional[int] = Field(default=None, gt=0)
    termCode: Optional[str] = None
    courseId: Optional[int] = Field(default=None, gt=0, description="管理员特殊补录必须选择具体课程版本")
    courseName: Optional[str] = None
    classId: Optional[int] = Field(default=None, gt=0)
    credit: Optional[float] = Field(default=None, ge=0)
    usualRatio: int = Field(default=30, ge=0, le=100)
    midtermRatio: int = Field(default=0, ge=0, le=100)
    finalRatio: int = Field(default=70, ge=0, le=100)
    passLine: int = Field(default=60, ge=0, le=100)
    adminSupplementReason: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_identity(self):
        if self.usualRatio + self.midtermRatio + self.finalRatio != 100:
            raise ValueError("平时、期中、期末比例之和必须为100")
        if not self.teachingTaskId:
            if not self.termId:
                raise ValueError("脱离教学任务补录必须绑定正式termId")
            if not self.courseId:
                raise ValueError("脱离教学任务补录必须选择课程库具体courseId")
            if len((self.adminSupplementReason or "").strip()) < 5:
                raise ValueError("管理员特殊补录原因不少于5字")
        return self


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


@router.post("/grade-tasks", summary="新建绑定稳定课程身份的成绩录入任务")
def grade_task_identity_create(
    body: GradeTaskIdentityCreateBody,
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(grade_service.create_grade_task(body, user), message="已创建")


@router.post("/makeup/batches/{batch_id}/enroll", summary="按原失败成绩纳入补考名单")
def makeup_identity_enroll(
    body: MakeupIdentityEnrollBody,
    batch_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.makeup.manage")),
):
    return success(
        makeup_service.enroll_makeup_by_grade(
            user, batch_id, body.gradeId, body.acadStudentId, body.originScore,
        ),
        message="已纳入",
    )


@router.post("/retake/apply", summary="按本人挂科成绩提交重修报名")
def retake_identity_apply(body: RetakeIdentityApplyBody, user=Depends(_student_only)):
    return success(makeup_service.retake_apply(user, body), message="重修报名已提交")


@router.post("/exemption/apply", summary="按课程库具体版本提交免修申请")
def exemption_identity_apply(body: ExemptionIdentityApplyBody, user=Depends(_student_only)):
    return success(makeup_service.exemption_apply(user, body), message="免修申请已提交")
