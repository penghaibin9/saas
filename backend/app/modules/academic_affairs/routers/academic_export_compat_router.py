"""阶段 7：教务旧同步导出的 ExportJob 兼容适配 Router。

本 Router 必须在大体量历史 ``academic_affairs.router`` 之前注册，精确遮蔽仍同步
返回 XLSX/ZIP 的旧路径。响应仍是文件，避免破坏现有页面；实际文件先进入公共
FileObject + ExportJob + 一次性票据链，并在响应头返回任务编号。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import require_permission
from app.modules.academic_affairs.routers import academic_affairs as base
from app.modules.academic_affairs.services.academic_export_compat_service import task_backed_file_response

router = APIRouter(prefix="/academic-affairs", tags=["教务中心·任务化兼容导出"])
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class PurposeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(..., min_length=5, max_length=500)


class RosterBody(PurposeBody):
    keyword: Optional[str] = None
    status: Optional[str] = None


class UnregisteredBody(PurposeBody):
    batchId: Optional[int] = None


class ScheduleBody(PurposeBody):
    scope: str
    identifier: str = Field(..., min_length=1)
    termId: Optional[str] = None
    weekStart: Optional[int] = Field(None, ge=1)
    weekEnd: Optional[int] = Field(None, ge=1)


class GradeAnalysisBody(PurposeBody):
    term: Optional[str] = None
    dimension: str = "course"


class StatsBody(PurposeBody):
    domain: Optional[str] = "overview"
    termId: Optional[int] = None
    collegeId: Optional[int] = None
    majorId: Optional[int] = None


class MakeupStatsBody(PurposeBody):
    term: Optional[str] = None
    collegeId: Optional[str] = None


class EvalBody(PurposeBody):
    domain: str


class QualityBody(PurposeBody):
    termId: Optional[str] = None
    collegeId: Optional[str] = None
    majorId: Optional[str] = None


def _response(*, content, filename, export_type, purpose, user, parameters=None, media_type=_XLSX):
    return task_backed_file_response(
        content=content,
        filename=filename,
        export_type=export_type,
        purpose=purpose,
        user=user,
        parameters=parameters,
        media_type=media_type,
    )


@router.post("/roster/export", summary="兼容旧页面：学籍名册导出进入 ExportJob")
def roster_export(body: RosterBody, user=Depends(require_permission(base._ROSTER_EXPORT))):
    content = base.svc.export_roster_xlsx(user, body.purpose, body.keyword, body.status)
    return _response(
        content=content, filename="roster_ledger.xlsx", export_type="ACADEMIC_ROSTER",
        purpose=body.purpose, user=user, parameters=body.model_dump(exclude={"purpose"}),
    )


@router.post("/registration/archive/{batchId}/export", summary="兼容旧页面：注册归档导出进入 ExportJob")
def registration_archive_export(
    body: PurposeBody,
    batchId: int = Path(...),
    user=Depends(require_permission(base._REG_ARCHIVE_EXPORT)),
):
    content = base.svc.export_registration_archive_xlsx(batchId, user, body.purpose)
    return _response(
        content=content, filename=f"registration_archive_{batchId}.xlsx",
        export_type="REGISTRATION_ARCHIVE", purpose=body.purpose, user=user,
        parameters={"batchId": batchId},
    )


@router.post("/registration/unregistered/export", summary="兼容旧页面：未注册名单导出进入 ExportJob")
def unregistered_export(body: UnregisteredBody, user=Depends(require_permission(base._REG_UNREG_EXPORT))):
    content = base.svc.export_unregistered_xlsx(user, body.batchId, body.purpose)
    return _response(
        content=content, filename="unregistered_students.xlsx", export_type="UNREGISTERED_STUDENTS",
        purpose=body.purpose, user=user, parameters={"batchId": body.batchId},
    )


@router.post("/schedule/export", summary="兼容旧页面：课表导出进入 ExportJob")
def schedule_export(body: ScheduleBody, user=Depends(require_permission(base._SCHED_EXPORT))):
    content = base.sched_svc.export_schedule(
        user, body.scope, body.identifier, body.termId, body.weekStart, body.weekEnd, body.purpose,
    )
    return _response(
        content=content, filename="schedule_export.xlsx", export_type="SCHEDULE",
        purpose=body.purpose, user=user, parameters=body.model_dump(exclude={"purpose"}),
    )


@router.post("/students/{studentId}/transcript/export", summary="兼容旧页面：学生成绩单进入 ExportJob")
def transcript_export(
    body: PurposeBody,
    studentId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.export")),
):
    content = base.grade_svc.export_transcript_xlsx(user, studentId, body.purpose)
    return _response(
        content=content, filename="student_transcript.xlsx", export_type="STUDENT_TRANSCRIPT",
        purpose=body.purpose, user=user, parameters={"studentId": studentId},
    )


@router.post("/grade-views/analysis/export", summary="兼容旧页面：成绩分析进入 ExportJob")
def grade_analysis_export(
    body: GradeAnalysisBody,
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    content = base.grade_svc.export_grade_analysis_xlsx(user, body.term, body.dimension, body.purpose)
    return _response(
        content=content, filename="grade_analysis.xlsx", export_type="GRADE_ANALYSIS",
        purpose=body.purpose, user=user, parameters=body.model_dump(exclude={"purpose"}),
    )


@router.post("/stats/export", summary="兼容旧页面：教务统计进入 ExportJob")
def stats_export(body: StatsBody, user=Depends(require_permission(base._STATS_EXPORT))):
    content = base.stats_svc.export_stats_xlsx(
        user, body.domain, body.termId, body.collegeId, body.majorId, body.purpose,
    )
    return _response(
        content=content, filename="academic_affairs_stats.xlsx", export_type="ACADEMIC_STATS",
        purpose=body.purpose, user=user, parameters=body.model_dump(exclude={"purpose"}),
    )


@router.post("/selection/batches/{batchId}/conflict-report/export", summary="兼容旧页面：选课冲突报表进入 ExportJob")
def selection_conflict_export(
    body: PurposeBody,
    batchId: int = Path(...),
    user=Depends(require_permission(base._SEL_VIEW)),
):
    content = base.selection_svc.export_conflict_report_xlsx(user, batchId, body.purpose)
    return _response(
        content=content, filename="selection_conflict_report.xlsx", export_type="SELECTION_CONFLICT_REPORT",
        purpose=body.purpose, user=user, parameters={"batchId": batchId},
    )


@router.post("/selection/archive/{batchId}/export", summary="兼容旧页面：选课归档进入 ExportJob")
def selection_archive_export(
    body: PurposeBody,
    batchId: int = Path(...),
    user=Depends(require_permission(base._SEL_MANAGE)),
):
    content = base.selection_svc.export_archive_xlsx(user, batchId, body.purpose)
    return _response(
        content=content, filename="selection_archive.xlsx", export_type="SELECTION_ARCHIVE",
        purpose=body.purpose, user=user, parameters={"batchId": batchId},
    )


@router.post("/makeup/stats/export", summary="兼容旧页面：补考重修统计进入 ExportJob")
def makeup_stats_export(body: MakeupStatsBody, user=Depends(require_permission(base._MK_EXPORT))):
    content = base.makeup_svc.export_makeup_stats_xlsx(user, body.term, body.collegeId, body.purpose)
    return _response(
        content=content, filename="makeup_stats.xlsx", export_type="MAKEUP_STATS",
        purpose=body.purpose, user=user, parameters=body.model_dump(exclude={"purpose"}),
    )


@router.post("/evaluation/batches/{bid}/export", summary="兼容旧页面：评教结果进入 ExportJob")
def evaluation_export(
    body: EvalBody,
    bid: int = Path(...),
    user=Depends(require_permission(base._EVAL_EXPORT)),
):
    content = base.evaluation_svc.export_evaluation_xlsx(user, bid, body.domain, body.purpose)
    return _response(
        content=content, filename=f"evaluation_{body.domain}_{bid}.xlsx", export_type="EVALUATION",
        purpose=body.purpose, user=user, parameters={"batchId": bid, "domain": body.domain},
    )


@router.post("/quality/reports/export", summary="兼容旧页面：质量报告进入 ExportJob")
def quality_report_export(body: QualityBody, user=Depends(require_permission(base._QUALITY_EXPORT))):
    content = base.quality_svc.export_report(
        user, body.termId, body.collegeId, body.majorId, body.purpose,
    )
    return _response(
        content=content, filename="academic_quality_report.xlsx", export_type="QUALITY_REPORT",
        purpose=body.purpose, user=user, parameters=body.model_dump(exclude={"purpose"}),
    )


@router.get("/quality/archive/export", summary="兼容旧页面：质量归档进入 ExportJob")
def quality_archive_export(
    domain: str = Query(...),
    termId: Optional[str] = Query(None),
    purpose: str = Query("旧页面兼容导出"),
    user=Depends(require_permission(base._QARCHIVE_EXPORT)),
):
    content = base.quality_svc.archive_export(user, domain, termId, purpose)
    return _response(
        content=content, filename=f"quality_archive_{domain}.xlsx", export_type="QUALITY_ARCHIVE",
        purpose=purpose, user=user, parameters={"domain": domain, "termId": termId},
    )


@router.get("/archive/batches/{bid}/export", summary="兼容旧页面：教务整包归档进入 ExportJob")
def archive_export_all(
    bid: int = Path(...),
    purpose: str = Query("旧页面兼容导出"),
    user=Depends(require_permission(base._ARCHIVE_EXPORT)),
):
    content, filename = base.archive_svc.export_batch_all(user, bid, purpose)
    return _response(
        content=content, filename=filename, export_type="ACADEMIC_ARCHIVE_ALL",
        purpose=purpose, user=user, parameters={"batchId": bid}, media_type="application/zip",
    )


@router.get("/archive/batches/{bid}/items/{category}/export", summary="兼容旧页面：教务单域归档进入 ExportJob")
def archive_export_item(
    bid: int = Path(...),
    category: str = Path(...),
    purpose: str = Query("旧页面兼容导出"),
    user=Depends(require_permission(base._ARCHIVE_EXPORT)),
):
    content, filename = base.archive_svc.export_batch_item(user, bid, category, purpose)
    return _response(
        content=content, filename=filename, export_type="ACADEMIC_ARCHIVE_ITEM",
        purpose=purpose, user=user, parameters={"batchId": bid, "category": category},
    )
