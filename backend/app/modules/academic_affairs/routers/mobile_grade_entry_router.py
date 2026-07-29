"""V2 R5 教师微信成绩录入补充端点。

保留既有单生录入和提交 URL，只新增整批事务保存与提交前质量报告。
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import mobile_academic_affairs_service as service

router = APIRouter(prefix="/mobile/teacher/academic", tags=["教师移动端-成绩录入"])


class MobileGradeRow(BaseModel):
    studentId: int = Field(..., gt=0)
    usualScore: Optional[int] = Field(default=None, ge=0, le=100)
    midtermScore: Optional[int] = Field(default=None, ge=0, le=100)
    finalScore: Optional[int] = Field(default=None, ge=0, le=100)
    exceptionFlag: Literal["NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"] = "NORMAL"


class MobileGradeBatchSaveBody(BaseModel):
    rows: list[MobileGradeRow] = Field(..., min_length=1, max_length=500)


@router.post("/grade-tasks/{task_id}/batch-save", summary="教师微信·成绩整批事务保存")
def mobile_grade_batch_save(
    body: MobileGradeBatchSaveBody,
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    rows = [row.model_dump() for row in body.rows]
    return success(service.teacher_grade_batch_save(task_id, user, rows), message="成绩已批量保存")


@router.get("/grade-tasks/{task_id}/quality-report", summary="教师微信·提交前成绩质量报告")
def mobile_grade_quality_report(
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(service.teacher_grade_quality_report(task_id, user))
