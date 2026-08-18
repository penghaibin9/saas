"""D8-S1 成绩任务主链 Move Only Router。

只迁出 legacy 大 Router 仍持有的成绩任务查询、名单、录分、Excel 导入、提交、审核、发布、退回与归档。
POST /grade-tasks 继续由 grade_task_create_v2_router 持有稳定课程身份请求合同；动态分项成绩、移动端录分、
成绩更正/复查与成绩读侧视图不在本批迁移范围。DTO、权限和 canonical grade_svc 全部复用 legacy。
C-W5 教师侧名单/回显/录入/导入/提交统一经 grade_execution；正式教学班已投影时教师权限只认
TeachingClassTeacher + 有效周次，尚未投影教学班的旧数据才允许 AaTeachingTask 迁移回退。
C-C3 安装 read consumer guards，把遗留学业 API、学生/家长摘要、资助资格、统计总览、挂科预警
拉回同一 EffectiveGrade ACTIVE-only + 冻结修读策略。
C-W4 复查运营台账只替换为有界 SQL 分页；成熟复查裁决命令保持唯一 Authority；人工催录复用
canonical AA_GRADE_ENTRY UnifiedTodo，不新造第二套任务系统。
遗留 /academic/grades 直接写 projection 的兼容入口保留 URL 但 fail-closed，禁止绕过正式发布/更正链。
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Path, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import academic_affairs_effective_grade_consumer_guard as effective_consumer_guard
from app.modules.academic_affairs.services import academic_affairs_effective_grade_external_consumer_guard as effective_external_guard
from app.modules.academic_affairs.services import academic_affairs_grade_change_live_authority as grade_change_live_authority
from app.modules.academic_affairs.services import academic_affairs_grade_execution_service as grade_exec_svc
from app.modules.academic_affairs.services import academic_affairs_grade_recheck_read_guard as grade_recheck_read_guard
from app.modules.academic_affairs.services import academic_affairs_grade_reminder_service as grade_reminder_svc
from app.modules.academic_affairs.services import academic_affairs_grade_task_read_service as grade_task_read_svc
from app.modules.academic_affairs.services import academic_affairs_grade_teacher_relation_guard as grade_teacher_relation_guard
from app.modules.academic_affairs.services import academic_affairs_legacy_grade_write_guard as legacy_grade_write_guard
from app.modules.academic_affairs.services import academic_affairs_warning_effective_grade_guard as warning_effective_guard
from app.services import xlsx_util

# shared services/__init__.py first installs mature grade/effective-grade extensions.
# C narrows only teacher write authority and legacy/cross-domain read-write compatibility boundaries;
# no shared registry or canonical EffectiveGrade algorithm is modified here.
grade_teacher_relation_guard.install()
grade_change_live_authority.install()
effective_consumer_guard.install()
effective_external_guard.install()
legacy_grade_write_guard.install()
warning_effective_guard.install()
grade_recheck_read_guard.install()

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-成绩主链"])

ScoreBody = legacy.ScoreBody
GradeImportErrorsBody = legacy.GradeImportErrorsBody
GradeImportRowsBody = legacy.GradeImportRowsBody
GradeReviewBody = legacy.GradeReviewBody
GradeReturnBody = legacy.GradeReturnBody

grade_svc = legacy.grade_svc
_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class GradeRemindBody(BaseModel):
    reason: str = Field(..., min_length=2, max_length=200)


@router.get("/grade-tasks", summary="成绩录入任务列表（按状态筛选，供审核/发布工作台队列）")
def grade_tasks(
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    items, total = grade_task_read_svc.list_tasks(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/grade-tasks/{taskId}/remind", summary="成绩催录（刷新当前正式任课教师待录待办）")
def grade_remind(
    body: GradeRemindBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    return success(
        grade_reminder_svc.remind_grade_entry(taskId, user, body.reason),
        message="已催录",
    )


@router.get("/grade-tasks/{taskId}/roster", summary="教学班学生名单（供录入圈定）")
def grade_roster(
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(grade_exec_svc.teacher_roster(taskId, user))


@router.get("/grade-tasks/{taskId}/records", summary="成绩录入表当前已录状态（供刷新/批量导入后回显）")
def grade_records(
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(grade_exec_svc.teacher_list_records(taskId, user))


@router.post("/grade-tasks/{taskId}/scores", summary="录入平时/期中/期末分（实时合成总评）")
def grade_enter_score(
    body: ScoreBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(grade_exec_svc.teacher_enter_score(taskId, user, body), message="已录入")


@router.get("/grade-tasks/{taskId}/import/template", summary="成绩批量导入·下载 Excel 模板(.xlsx)")
def grade_import_template(
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    data = xlsx_util.build_template_xlsx(
        grade_svc.IMPORT_HEADERS,
        sample=grade_svc.IMPORT_SAMPLE,
        notes=grade_svc.IMPORT_NOTES,
        required=grade_svc.IMPORT_REQUIRED,
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": "attachment; filename=grade_import_template.xlsx"},
    )


@router.post("/grade-tasks/{taskId}/import/xlsx", summary="上传 Excel(.xlsx)·解析并预校验（不写库）")
async def grade_import_xlsx(
    taskId: int = Path(...),
    file: UploadFile = File(...),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    content = await xlsx_util.read_safe_upload(file)
    rows = xlsx_util.read_xlsx(content, grade_svc.IMPORT_HEADER_MAP)
    return success({**grade_exec_svc.teacher_grade_import_dry_run(taskId, user, rows), "rows": rows})


@router.post("/grade-tasks/{taskId}/import/errors-xlsx", summary="下载错误行 Excel(.xlsx)")
def grade_import_errors_xlsx(
    body: GradeImportErrorsBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    data = xlsx_util.build_error_rows_xlsx(
        grade_svc.IMPORT_HEADERS,
        body.rows,
        body.errors,
        grade_svc._row_values_for_error,
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": "attachment; filename=grade_import_errors.xlsx"},
    )


@router.post("/grade-tasks/{taskId}/import/confirm", summary="成绩批量导入·确认（整批事务，逐行落正式成绩记录）")
def grade_import_confirm(
    body: GradeImportRowsBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    return success(grade_exec_svc.teacher_grade_import_confirm(taskId, user, body.rows), message="导入完成")


@router.post("/grade-tasks/{taskId}/submit", summary="提交成绩进入学院审核")
def grade_submit(
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.submit")),
):
    return success(grade_exec_svc.teacher_submit_task(taskId, user), message="已提交")


@router.post("/grade-tasks/{taskId}/college-review", summary="学院审核成绩（通过/退回）")
def grade_college_review(
    body: GradeReviewBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.collegeReview")),
):
    return success(
        grade_svc.college_review(taskId, user, body.action, body.reason or ""),
        message="已处理",
    )


@router.post("/grade-tasks/{taskId}/publish", summary="教务处终审发布（原子回写+台账刷新+预警）")
def grade_publish(
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.publish")),
):
    return success(grade_svc.publish_grades(taskId, user), message="已发布")


@router.post("/grade-tasks/{taskId}/return", summary="教务处退回（教务终审阶段）")
def grade_return(
    body: GradeReturnBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.return")),
):
    return success(grade_svc.return_task(taskId, user, body.reason), message="已退回")


@router.post("/grade-tasks/{taskId}/archive", summary="学期归档（仅已发布任务）")
def grade_archive(
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.archive")),
):
    return success(grade_svc.archive_task(taskId, user), message="已归档")
