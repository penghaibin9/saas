"""V2 R5 / C-W5 教师微信成绩录入补充端点。

既有 legacy 单生录入/提交 URL 继续保留兼容；C-W5 新增 ``grade-execution``
同源入口，任务列表、名单回显、单生保存、整批保存、质量报告和提交全部统一走
Grade Execution live-owner authority。这样教师替换后旧教师立即失权，新教师无需改写
AaGradeTask.teacher_key 历史快照即可继续 canonical 成绩状态机。
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_grade_execution_service as service
from app.modules.academic_affairs.services import academic_affairs_grade_task_read_service as read_service

router = APIRouter(prefix="/mobile/teacher/academic", tags=["教师移动端-成绩录入"])


class MobileGradeRow(BaseModel):
    studentId: int = Field(..., gt=0)
    usualScore: Optional[int] = Field(default=None, ge=0, le=100)
    midtermScore: Optional[int] = Field(default=None, ge=0, le=100)
    finalScore: Optional[int] = Field(default=None, ge=0, le=100)
    exceptionFlag: Literal["NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"] = "NORMAL"


class MobileGradeBatchSaveBody(BaseModel):
    rows: list[MobileGradeRow] = Field(..., min_length=1, max_length=500)


def _merged_roster(task_id: int, user) -> dict:
    roster = service.teacher_roster(task_id, user)
    records = service.teacher_list_records(task_id, user)
    record_by_student = {
        str(row.get("studentId")): row
        for row in (records.get("items") or [])
        if row.get("studentId") not in (None, "")
    }
    items = []
    for student in roster.get("items") or []:
        item = dict(student)
        record = record_by_student.get(str(student.get("studentId")))
        if record:
            item.update(
                {
                    "usualScore": record.get("usualScore"),
                    "midtermScore": record.get("midtermScore"),
                    "finalScore": record.get("finalScore"),
                    "totalScore": record.get("totalScore"),
                    "passStatus": record.get("passStatus"),
                    "exceptionFlag": record.get("exceptionFlag") or "NORMAL",
                }
            )
        items.append(item)
    return {
        "items": items,
        "note": roster.get("note") or "",
        "usualRatio": records.get("usualRatio", roster.get("usualRatio")),
        "midtermRatio": records.get("midtermRatio", roster.get("midtermRatio")),
        "finalRatio": records.get("finalRatio", roster.get("finalRatio")),
        "status": records.get("status") or roster.get("status") or "",
    }


@router.get("/grade-execution/tasks", summary="教师微信·本人实时成绩任务")
def mobile_grade_execution_tasks(
    status: Optional[str] = Query(default=None),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    items, total = read_service.list_tasks(user, status=status, page=1, page_size=100)
    return success({"items": items, "total": total})


@router.get("/grade-execution/tasks/{task_id}/roster", summary="教师微信·实时成绩名单与已录回显")
def mobile_grade_execution_roster(
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(_merged_roster(task_id, user))


@router.post("/grade-execution/tasks/{task_id}/scores", summary="教师微信·实时单生成绩保存")
def mobile_grade_execution_score(
    body: MobileGradeRow,
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(service.teacher_enter_score(task_id, user, body), message="成绩已保存")


@router.post("/grade-execution/tasks/{task_id}/batch-save", summary="教师微信·实时成绩整批事务保存")
def mobile_grade_execution_batch_save(
    body: MobileGradeBatchSaveBody,
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    rows = [row.model_dump() for row in body.rows]
    return success(service.teacher_grade_batch_save(task_id, user, rows), message="成绩已批量保存")


@router.get("/grade-execution/tasks/{task_id}/quality-report", summary="教师微信·实时提交前成绩质量报告")
def mobile_grade_execution_quality_report(
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(service.teacher_grade_quality_report(task_id, user))


@router.post("/grade-execution/tasks/{task_id}/submit", summary="教师微信·实时提交成绩进入学院审核")
def mobile_grade_execution_submit(
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.submit")),
):
    report = service.teacher_grade_quality_report(task_id, user)
    if not report.get("canSubmit"):
        from app.core.exceptions import AppException

        raise AppException(
            "DATA_CONFLICT",
            report.get("summary") or "成绩尚未录全，暂不可提交学院审核",
            details=report,
            http_status=409,
        )
    return success(service.teacher_submit_task(task_id, user), message="已提交学院审核")


# 兼容已经发布给客户端的 V2 R5 两个补充 URL；内部仍与新 execution 入口同源。
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
