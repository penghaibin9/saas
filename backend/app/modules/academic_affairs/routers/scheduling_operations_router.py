"""D5-S2 自动排课 / 排课增强 Move Only Router。

只迁出 legacy 大 Router 已有的教师可用时间、冲突报告、排课增强、Excel 结果导入、
教师异议、正式归档与自动排课入口。DTO、权限码、canonical service 与响应形状全部复用原合同。
/scheduling/rules 继续由 scheduling_rule_router 持有；课表主链继续由 schedule_core_router 持有。
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Path, UploadFile
from fastapi.responses import StreamingResponse

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.routers import academic_affairs as legacy

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-排课增强"])

# Move Only：DTO / service / 常量直接复用 legacy，避免结构拆分时复制业务规则。
AvailabilityBody = legacy.AvailabilityBody
AvailReviewBody = legacy.AvailReviewBody
TeacherObjectBody = legacy.TeacherObjectBody
AdjustItemBody = legacy.AdjustItemBody

sched_svc = legacy.sched_svc
scheduling_svc = legacy.scheduling_svc
autosched_svc = legacy.autosched_svc
xlsx_util = legacy.xlsx_util
AppException = legacy.AppException

_XLSX_MEDIA = legacy._XLSX_MEDIA
_SCHED_RULE = legacy._SCHED_RULE
_SCHED_AVAIL = legacy._SCHED_AVAIL
_SCHED_VIEW = legacy._SCHED_VIEW
_SCHED_EDIT = legacy._SCHED_EDIT
_SCHED_IMPORT = legacy._SCHED_IMPORT
_SCHED_ARCHIVE = legacy._SCHED_ARCHIVE
_SCHED_TEACHER_CONFIRM = legacy._SCHED_TEACHER_CONFIRM


# ── 教师可用时间 ──
@router.post("/scheduling/teacher-availability", summary="教师提交不可排课时段")
def sched_avail_submit(
    body: AvailabilityBody,
    user=Depends(require_permission(_SCHED_TEACHER_CONFIRM)),
):
    return success(scheduling_svc.submit_availability(user, body), message="已提交")


@router.get("/scheduling/teacher-availability/my", summary="我提交的可用时间")
def sched_avail_my(
    termId: Optional[str] = None,
    user=Depends(require_permission(_SCHED_TEACHER_CONFIRM)),
):
    return success({"items": scheduling_svc.list_availability(user, termId, mine=True)})


@router.get("/scheduling/teacher-availability", summary="教师可用时间汇总（学院采纳）")
def sched_avail_list(
    termId: Optional[str] = None,
    teacherKey: Optional[str] = None,
    status: Optional[str] = None,
    user=Depends(require_permission(_SCHED_AVAIL)),
):
    return success({"items": scheduling_svc.list_availability(user, termId, teacherKey, status)})


@router.post("/scheduling/teacher-availability/{aid}/review", summary="采纳/驳回教师可用时间")
def sched_avail_review(
    body: AvailReviewBody,
    aid: int = Path(...),
    user=Depends(require_permission(_SCHED_AVAIL)),
):
    return success(scheduling_svc.review_availability(user, aid, body.action, body.reason), message="已处理")


# ── 冲突与排课结果增强 ──
@router.get("/scheduling/batches/{bid}/conflict-report", summary="批次全量冲突报告（HARD/SOFT 分级）")
def sched_conflict_report(
    bid: int = Path(...),
    user=Depends(require_permission(_SCHED_VIEW)),
):
    return success(scheduling_svc.conflict_report(user, bid))


@router.get("/schedule-batches/{batchId}/room-view", summary="教室占用查询（05号卡：辅助人工排课选教室）")
def schedule_room_view(
    batchId: int = Path(...),
    classroom: str = "",
    user=Depends(require_permission(_SCHED_VIEW)),
):
    return success(sched_svc.room_view(batchId, user, classroom))


@router.get("/schedule-batches/{batchId}/summary", summary="排课结果汇总统计（10号卡：预发布前核对）")
def schedule_summary(
    batchId: int = Path(...),
    user=Depends(require_permission(_SCHED_VIEW)),
):
    return success(scheduling_svc.summary(user, batchId))


# ── Excel 排课结果导入 ──
@router.get("/schedule-batches/import/template", summary="排课结果导入模板下载（07号卡）")
def schedule_import_template(
    user=Depends(require_permission(_SCHED_IMPORT)),
):
    data = xlsx_util.build_template_xlsx(
        sched_svc.IMPORT_HEADERS,
        sample=sched_svc.IMPORT_SAMPLE,
        notes=sched_svc.IMPORT_NOTES,
        required=sched_svc.IMPORT_REQUIRED,
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": "attachment; filename=schedule_import_template.xlsx"},
    )


@router.post("/schedule-batches/{batchId}/import/xlsx", summary="上传Excel导入排课结果（07号卡：自动排课预留=结果导入通道）")
async def schedule_import_xlsx(
    batchId: int = Path(...),
    file: UploadFile = File(...),
    user=Depends(require_permission(_SCHED_IMPORT)),
):
    content = await file.read()
    rows = xlsx_util.read_xlsx(content, sched_svc.IMPORT_HEADER_MAP)
    if len(rows) > sched_svc.IMPORT_MAX_ROWS:
        raise AppException("VALIDATION_ERROR", f"单批导入行数不得超过 {sched_svc.IMPORT_MAX_ROWS} 行")
    rows = sched_svc.sanitize_import_rows(rows)
    return success(sched_svc.import_items(batchId, user, rows), message="导入完成")


# ── 教师异议与定点改排 ──
@router.post("/schedule-batches/{batchId}/teacher-object", summary="教师对本人课表提出异议（11号卡）")
def schedule_teacher_object(
    body: TeacherObjectBody,
    batchId: int = Path(...),
    user=Depends(require_permission(_SCHED_TEACHER_CONFIRM)),
):
    return success(sched_svc.teacher_object(batchId, user, body.itemId, body.reason), message="异议已提交")


@router.get("/schedule-batches/{batchId}/objections", summary="本批次待处理教师异议清单（11号卡）")
def schedule_objections(
    batchId: int = Path(...),
    user=Depends(require_permission(_SCHED_VIEW)),
):
    return success({"items": sched_svc.list_objections(batchId, user)})


@router.put("/schedule-batches/{batchId}/items/{itemId}", summary="排课调整（11号卡：处理教师异议定点改排）")
def schedule_adjust_item(
    body: AdjustItemBody,
    batchId: int = Path(...),
    itemId: int = Path(...),
    user=Depends(require_permission(_SCHED_EDIT)),
):
    return success(
        sched_svc.adjust_item(
            batchId,
            itemId,
            user,
            body.weekday,
            body.slotNo,
            body.classroom,
            body.weekParity,
        ),
        message="已改排",
    )


@router.post("/schedule-batches/{batchId}/archive", summary="排课归档（13号卡：学期结束正式归档）")
def schedule_archive(
    batchId: int = Path(...),
    user=Depends(require_permission(_SCHED_ARCHIVE)),
):
    return success(sched_svc.archive(batchId, user), message="已归档")


# ── 自动排课引擎 ──
@router.get("/scheduling/rule-catalog", summary="排课参数说明书（供参数面板渲染）")
def sched_rule_catalog(
    user=Depends(require_permission(_SCHED_VIEW)),
):
    return success(autosched_svc.rule_catalog(user))


@router.get("/scheduling/batches/{bid}/miss-report", summary="漏排数据分析（只读试排，不落库）")
def sched_miss_report(
    bid: int = Path(...),
    user=Depends(require_permission(_SCHED_VIEW)),
):
    return success(autosched_svc.miss_report(user, bid))


@router.post("/scheduling/batches/{bid}/auto", summary="自动编排课表（增量续排；dryRun 只算不落）")
def sched_auto(
    bid: int = Path(...),
    dryRun: bool = False,
    user=Depends(require_permission(_SCHED_RULE)),
):
    result = autosched_svc.auto_schedule(user, bid, dry_run=dryRun)
    message = (
        "试排完成（未落库）"
        if dryRun
        else f"已排入 {result['placedSessions']} 节，漏排 {result['missedTasks']} 个任务"
    )
    return success(result, message=message)


@router.delete("/scheduling/batches/{bid}/auto", summary="清除自动排课结果（仅 AUTO 项，人工排课保留）")
def sched_auto_clear(
    bid: int = Path(...),
    user=Depends(require_permission(_SCHED_RULE)),
):
    return success(autosched_svc.clear_auto_items(user, bid), message="已清除自动排课结果")
