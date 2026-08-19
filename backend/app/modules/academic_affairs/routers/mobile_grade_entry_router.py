"""V2 R5 / C-W5 教师微信成绩录入补充端点。

既有 legacy 单生录入/提交 URL 继续保留兼容；C-W5 新增 ``grade-execution``
同源入口，任务列表、名单回显、单生保存、整批保存、质量报告和提交全部统一走
Grade Execution live-owner authority。正式教学班存在时只认 TeachingClassTeacher + 有效周次；
尚未投影教学班的历史数据才允许 AaTeachingTask 迁移回退。

C-W4 deadline 同样覆盖新旧移动端提交入口：质量报告显式投影逾期状态，真正提交统一经
GradeTask deadline Authority；MySQL status trigger 是最终原子边界，移动端不直接暴露 DB 异常。

该 extension router 也是 C 线执行 guard 的稳定启动点。考勤 command/read 已由 public
facade 显式委托最终 Owner，不再通过启动顺序 monkey-patch；这里只把移动端考勤 picker
绑定到同一 relation-first Teacher Today Authority。工作量和成绩 Todo guard 仍按其既有
兼容安装合同生效。

老版本客户端仍可能调用 ``/mobile/teacher/academic/grade-tasks/*``。本模块在启动时
只重绑这些 legacy service 函数到同一 live authority，不删 URL、不复制成绩状态机，
从而避免兼容入口变成旧教师绕过正式任课关系或 deadline 的后门。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.exceptions import AppException, no_permission
from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_attendance_teacher_relation_guard as attendance_relation_guard
from app.modules.academic_affairs.services import academic_affairs_grade_deadline_service as deadline_service
from app.modules.academic_affairs.services import academic_affairs_grade_execution_service as service
from app.modules.academic_affairs.services import academic_affairs_grade_task_read_service as read_service
from app.modules.academic_affairs.services import academic_affairs_grade_teacher_relation_guard as teacher_relation_guard
from app.modules.academic_affairs.services import academic_affairs_grade_todo_teacher_relation_guard as grade_todo_relation_guard
from app.modules.academic_affairs.services import academic_affairs_workload_teacher_relation_guard as workload_relation_guard
from app.modules.academic_affairs.services import mobile_academic_affairs_facade as mobile_facade
from app.modules.academic_affairs.services import mobile_academic_affairs_public_service as mobile_public

# This router can be imported before the PC grade router; install the formal grade/workload
# adapters locally so runtime execution never depends on router order. Attendance command/read
# already have explicit public delegates; only the mobile picker needs a compatibility binding.
teacher_relation_guard.install()
mobile_public.teacher_attendance_class_options = attendance_relation_guard.teacher_attendance_class_options
mobile_facade.teacher_attendance_class_options = attendance_relation_guard.teacher_attendance_class_options
workload_relation_guard.install()
grade_todo_relation_guard.install()

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


def _quality_report_with_deadline(task_id: int, user) -> dict:
    report = service.teacher_grade_quality_report(task_id, user)
    deadline = deadline_service.task_deadline_projection(task_id, status=report.get("status"))
    report.update(deadline)
    if deadline.get("isOverdue") is True:
        report["canSubmit"] = False
        report["summary"] = "成绩录入已超过截止时间，请联系学院/教务延期后再提交"
    return report


def _legacy_teacher_grade_tasks(user, status=None):
    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    items, total = read_service.list_tasks(user, status=status, page=1, page_size=100)
    return {"items": items, "total": total}


def _legacy_teacher_grade_roster(task_id, user) -> dict:
    return _merged_roster(int(task_id), user)


def _legacy_teacher_grade_records(task_id, user) -> dict:
    return service.teacher_list_records(int(task_id), user)


def _legacy_teacher_grade_enter_score(task_id, user, body) -> dict:
    payload = body or {}
    if not payload.get("studentId"):
        raise AppException("VALIDATION_ERROR", "studentId 必填")
    return service.teacher_enter_score(int(task_id), user, SimpleNamespace(**payload))


def _legacy_teacher_grade_submit_task(task_id, user) -> dict:
    return deadline_service.teacher_submit_task(int(task_id), user)


def _install_legacy_live_grade_compat() -> None:
    mobile_public.teacher_grade_tasks = _legacy_teacher_grade_tasks
    mobile_public.teacher_grade_roster = _legacy_teacher_grade_roster
    mobile_public.teacher_grade_records = _legacy_teacher_grade_records
    mobile_public.teacher_grade_enter_score = _legacy_teacher_grade_enter_score
    mobile_public.teacher_grade_submit_task = _legacy_teacher_grade_submit_task


_install_legacy_live_grade_compat()


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
    return success(_quality_report_with_deadline(task_id, user))


@router.post("/grade-execution/tasks/{task_id}/submit", summary="教师微信·实时提交成绩进入学院审核")
def mobile_grade_execution_submit(
    task_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.grade.submit")),
):
    report = _quality_report_with_deadline(task_id, user)
    if not report.get("canSubmit"):
        raise AppException(
            "DATA_CONFLICT",
            report.get("summary") or "成绩尚未录全，暂不可提交学院审核",
            details=report,
            http_status=409,
        )
    return success(deadline_service.teacher_submit_task(task_id, user), message="已提交学院审核")


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
    return success(_quality_report_with_deadline(task_id, user))
