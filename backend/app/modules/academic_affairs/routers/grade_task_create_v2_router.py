"""成绩任务创建 V2 入口。

历史大 Router 的 GradeTaskCreate 没有 ``courseId`` 字段，导致管理员按稳定课程版本做特殊补录时，
请求在 Pydantic 层就丢失 courseId / 被 courseName 校验提前 422，永远到不了生产 Service 的
课程身份校验与 archived-term 写保护。该精确适配器只修请求合同，不复制成绩业务逻辑：
仍统一调用 ``academic_affairs_grade_service.create_grade_task``。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])


class GradeTaskCreateV2(BaseModel):
    teachingTaskId: Optional[str] = None
    termId: Optional[str] = None
    termCode: Optional[str] = None
    courseId: Optional[str] = Field(None, description="课程库稳定课程版本ID；管理员特殊补录必须使用该身份")
    courseName: Optional[str] = Field(None, min_length=1, description="展示名；传 teachingTaskId/courseId 时由服务端权威解析")
    classId: Optional[str] = None
    credit: Optional[float] = None
    usualRatio: int = Field(30, ge=0, le=100)
    midtermRatio: int = Field(0, ge=0, le=100)
    finalRatio: int = Field(70, ge=0, le=100)
    passLine: int = Field(60, ge=0, le=100)
    adminSupplementReason: Optional[str] = Field(None, description="管理员脱离教学任务补录原因，不少于5字")

    @model_validator(mode="after")
    def _require_course_or_task(self):
        if not self.teachingTaskId and not self.courseId and not (self.courseName or "").strip():
            raise ValueError("courseId/courseName 与 teachingTaskId 至少填一项")
        if not self.teachingTaskId and not (self.termId or "").strip():
            raise ValueError("脱离教学任务补录必须填写正式 termId")
        return self


@router.post("/grade-tasks", summary="新建成绩录入任务（稳定课程身份 V2）")
def grade_task_create_v2(
    body: GradeTaskCreateV2,
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(grade_svc.create_grade_task(body, user), message="已创建")
