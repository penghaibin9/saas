"""成绩任务稳定课程身份入口。

原 ``POST /grade-tasks`` 保持教学任务创建兼容；管理员脱离教学任务特殊补录必须使用本入口，
显式携带课程库 ``courseId``、正式 ``termId`` 和补录原因，避免旧请求模型丢弃稳定身份字段。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_service

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-成绩身份"])


class GradeTaskIdentityCreateBody(BaseModel):
    teachingTaskId: Optional[int] = Field(default=None, gt=0)
    termId: Optional[int] = Field(default=None, gt=0)
    termCode: Optional[str] = None
    courseId: Optional[int] = Field(default=None, gt=0, description="管理员特殊补录必须选择课程库具体版本")
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
            if not self.classId:
                raise ValueError("管理员特殊补录必须选择明确行政班classId")
            if len((self.adminSupplementReason or "").strip()) < 5:
                raise ValueError("管理员特殊补录原因不少于5字")
        return self


@router.post("/grade-tasks/identity", summary="新建绑定稳定课程身份的成绩任务")
def create_grade_task_with_identity(
    body: GradeTaskIdentityCreateBody,
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(grade_service.create_grade_task(body, user), message="已创建")
