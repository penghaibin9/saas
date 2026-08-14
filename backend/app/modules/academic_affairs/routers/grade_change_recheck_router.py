"""D8-S3 成绩更正 / 成绩复查 Move Only Router。

仅迁出历史大 Router 仍持有的成绩更正三段写链与成绩复查 PC 台账/复审入口。
DTO、权限、canonical service、状态机、审计及并发保护全部复用既有实现；成绩认定/课程替代
继续留给 D8-S4，成绩任务主链/读侧/导出/dynamic/mobile owner 不在本批改动。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-成绩更正复查"])

grade_svc = legacy.grade_svc
recheck_svc = legacy.recheck_svc
GradeChangeRequestBody = legacy.GradeChangeRequestBody
GradeChangeReviewBody = legacy.GradeChangeReviewBody
GradeRecheckReviewBody = legacy.GradeRecheckReviewBody


@router.post("/grade-tasks/{taskId}/records/{recordId}/change-request", summary="教师发起成绩更正")
def grade_change_request(
    body: GradeChangeRequestBody,
    taskId: int = Path(...),
    recordId: int = Path(...),
    user=Depends(require_permission("academicAffairs.gradeChange.apply")),
):
    return success(grade_svc.change_request(taskId, recordId, user, body), message="更正申请已提交")


@router.post("/grade-change/{recordId}/college-review", summary="成绩更正学院初审")
def grade_change_college_review(
    body: GradeChangeReviewBody,
    recordId: int = Path(...),
    user=Depends(require_permission("academicAffairs.gradeChange.review")),
):
    return success(
        grade_svc.change_college_review(recordId, user, body.action, body.reason or ""),
        message="已处理",
    )


@router.post("/grade-change/{recordId}/academic-review", summary="成绩更正教务处终审")
def grade_change_academic_review(
    body: GradeChangeReviewBody,
    recordId: int = Path(...),
    user=Depends(require_permission("academicAffairs.gradeChange.review")),
):
    return success(
        grade_svc.change_academic_review(recordId, user, body.action, body.reason or ""),
        message="已处理",
    )


@router.get("/grade-rechecks", summary="成绩复查台账（教务处，按状态筛选）")
def grade_recheck_list(
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    items, total = recheck_svc.list_all(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/grade-rechecks/{recheckId}/review", summary="成绩复查复审（维持/调整回写t_acad_grade+通知学生/不予受理）")
def grade_recheck_review(
    body: GradeRecheckReviewBody,
    recheckId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.publish")),
):
    return success(recheck_svc.review(user, recheckId, body.action, body.note, body.newScore))
