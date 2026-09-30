"""D8-S3 成绩更正 / 成绩复查 Move Only Router。

仅迁出历史大 Router 仍持有的成绩更正三段写链与成绩复查 PC 台账/复审入口。
DTO、权限、canonical service、状态机、审计及并发保护全部复用既有实现；成绩认定/课程替代
继续留给 D8-S4，成绩任务主链/读侧/导出/dynamic/mobile owner 不在本批改动。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Path, Query

from app.core.permissions import require_any_permission, require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import academic_affairs_grade_recheck_read_service as recheck_read_svc
from app.modules.academic_affairs.services import academic_affairs_grade_change_read_service as change_read_svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-成绩更正复查"])

grade_svc = legacy.grade_svc
recheck_svc = legacy.recheck_svc
GradeChangeRequestBody = legacy.GradeChangeRequestBody
GradeChangeReviewBody = legacy.GradeChangeReviewBody
GradeRecheckReviewBody = legacy.GradeRecheckReviewBody


def _change_identity(body):
    return {key: getattr(body, key) for key in (
        "changeRequestId", "expectedRequestVersion", "currentTaskId", "expectedTaskVersion",
    )}


@router.get("/grade-changes", summary="成绩更正申请队列（真实范围与分页）")
def grade_change_list(
    queue: str = "MINE", status: Optional[str] = None,
    taskId: Optional[int] = Query(None, gt=0), recordId: Optional[int] = Query(None, gt=0),
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    user=Depends(require_any_permission("academicAffairs.gradeChange.apply", "academicAffairs.gradeChange.review")),
):
    items, total = change_read_svc.list_requests(
        user, queue=queue, status=status, task_id=taskId, record_id=recordId, page=page, page_size=pageSize,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/grade-changes/{changeRequestId}/detail", summary="成绩更正精确申请及审批证据")
def grade_change_detail(
    changeRequestId: int = Path(..., gt=0),
    user=Depends(require_any_permission("academicAffairs.gradeChange.apply", "academicAffairs.gradeChange.review")),
):
    return success(change_read_svc.get_detail(user, changeRequestId))


@router.get("/grade-tasks/{taskId}/records/{recordId}/change-source", summary="成绩更正精确来源及正式版本")
def grade_change_source(
    taskId: int = Path(..., gt=0), recordId: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.gradeChange.apply")),
):
    return success(change_read_svc.get_source(user, taskId, recordId))


@router.post("/grade-tasks/{taskId}/records/{recordId}/change-request", summary="教师发起成绩更正")
def grade_change_request(
    body: GradeChangeRequestBody,
    taskId: int = Path(...),
    recordId: int = Path(...),
    command_key: Optional[str] = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
    user=Depends(require_permission("academicAffairs.gradeChange.apply")),
):
    return success(grade_svc.change_request(taskId, recordId, user, body, command_key=command_key), message="更正申请已提交")


@router.post("/grade-change/{recordId}/college-review", summary="成绩更正学院初审")
def grade_change_college_review(
    body: GradeChangeReviewBody,
    recordId: int = Path(...),
    command_key: Optional[str] = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
    user=Depends(require_permission("academicAffairs.gradeChange.review")),
):
    return success(
        grade_svc.change_college_review(recordId, user, body.action, body.reason or "", identity=_change_identity(body), command_key=command_key),
        message="已处理",
    )


@router.post("/grade-change/{recordId}/academic-review", summary="成绩更正教务处终审")
def grade_change_academic_review(
    body: GradeChangeReviewBody,
    recordId: int = Path(...),
    command_key: Optional[str] = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
    user=Depends(require_permission("academicAffairs.gradeChange.review")),
):
    return success(
        grade_svc.change_academic_review(recordId, user, body.action, body.reason or "", identity=_change_identity(body), command_key=command_key),
        message="已处理",
    )


@router.get("/grade-rechecks", summary="成绩复查台账（教务处，按状态筛选）")
def grade_recheck_list(
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    items, total = recheck_read_svc.list_all(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/grade-rechecks/{recheckId}/review", summary="成绩复查复审（维持/调整回写t_acad_grade+通知学生/不予受理）")
def grade_recheck_review(
    body: GradeRecheckReviewBody,
    recheckId: int = Path(...),
    command_key: Optional[str] = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
    user=Depends(require_permission("academicAffairs.grade.publish")),
):
    return success(recheck_svc.review(user, recheckId, body.action, body.note, body.newScore, command_key=command_key))


@router.get("/grade-rechecks/{recheckId}/detail", summary="成绩复查精确申请详情")
def grade_recheck_detail(
    recheckId: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    return success(recheck_read_svc.get_detail(user, recheckId))
