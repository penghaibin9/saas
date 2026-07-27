"""R10 动态成绩项接口。"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_dynamic_grade_service as service
from app.modules.academic_affairs.services import academic_affairs_dynamic_grade_roster_service as roster_service

router = APIRouter(prefix="/academic-affairs/grade-tasks", tags=["教务中心-动态成绩"])


class GradeComponentBody(BaseModel):
    code: str = Field(..., min_length=2, max_length=40)
    name: str = Field(..., min_length=1, max_length=80)
    weight: float = Field(..., gt=0, le=100)
    required: bool = True
    order: int | None = Field(default=None, ge=1, le=99)


class GradeSchemeBody(BaseModel):
    components: list[GradeComponentBody] = Field(..., min_length=1, max_length=12)


class DynamicScoreBody(BaseModel):
    studentId: int = Field(..., gt=0)
    scores: dict[str, Any] = Field(default_factory=dict)
    exceptionFlag: Literal["NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"] = "NORMAL"


@router.get("/{task_id}/scheme", summary="动态成绩项方案")
def dynamic_grade_scheme(
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(service.get_scheme(task_id, user))


@router.put("/{task_id}/scheme", summary="配置动态成绩项（首次录分前）")
def dynamic_grade_scheme_update(
    body: GradeSchemeBody,
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(
        service.configure_scheme(task_id, user, [item.model_dump() for item in body.components]),
        message="成绩项方案已保存",
    )


@router.get("/{task_id}/component-roster", summary="动态成绩项正式名单与分项回显")
def dynamic_grade_component_roster(
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(roster_service.component_roster(task_id, user))


@router.post("/{task_id}/component-scores", summary="录入学生动态分项成绩")
def dynamic_grade_enter(
    body: DynamicScoreBody,
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(
        service.enter_component_scores(
            task_id, user, body.studentId, body.scores, body.exceptionFlag,
        ),
        message="分项成绩已保存",
    )


@router.get("/{task_id}/students/{student_id}/component-scores", summary="查看学生动态分项成绩")
def dynamic_grade_student_scores(
    task_id: int = Path(..., gt=0),
    student_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(service.student_component_scores(task_id, user, student_id))
