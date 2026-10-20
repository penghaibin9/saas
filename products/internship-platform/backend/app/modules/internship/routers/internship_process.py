"""岗位实习中心 · 过程报告 + 实习变更 API（/api/v1/internship/process-reports/*、/change-requests/*）。

过程报告（月报/总结等）：学生端提交(mobile) → 教师/管理端复核。
实习变更（换单位/换岗位）：学生端申请(mobile) → 教师/管理端审批。
数据范围与状态机由 service 处理。PC 管理端（学生 403 由注册处 require_staff 统一门禁）。

权限（P3）：报告查询 internship.report.view、复核 internship.report.review、导出 internship.report.export；
变更查询 internship.change.view、审批 internship.change.review。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_change_service as change_svc
from app.modules.internship.services import internship_process_report_service as report_svc
from app.modules.internship.services import internship_report_quality_service as quality_svc

router = APIRouter(prefix="/internship", tags=["岗位实习-过程报告与变更"])

_P_REPORT_VIEW = "internship.report.view"
_P_REPORT_REVIEW = "internship.report.review"
_P_REPORT_EXPORT = "internship.report.export"
_P_CHANGE_VIEW = "internship.change.view"
_P_CHANGE_REVIEW = "internship.change.review"


# ── 报告批阅绩效（周报 + 日报/月报/总结，不可变批阅事实） ──
@router.get("/report-review-performance", summary="报告批阅绩效（按批次与数据范围）")
def report_review_performance(
    batchId: str = Query(..., min_length=1),
    user=Depends(require_permission(_P_REPORT_VIEW)),
):
    return success(quality_svc.report_review_performance(user, batchId))


@router.post("/report-review-performance/export", summary="导出报告批阅绩效 Excel")
def report_review_performance_export(
    batchId: str = Query(..., min_length=1),
    user=Depends(require_permission(_P_REPORT_EXPORT)),
):
    return success(quality_svc.export_report_review_performance(user, batchId))


@router.get("/report-obligations", summary="报告应交/实交/未交台账")
def report_obligations(
    batchId: str = Query(..., min_length=1),
    keyword: Optional[str] = None,
    missingOnly: bool = Query(False),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
    user=Depends(require_permission(_P_REPORT_VIEW)),
):
    return success(quality_svc.report_obligations(
        user, batchId, keyword=keyword or "", missing_only=missingOnly,
        page=page, page_size=pageSize,
    ))


@router.post("/report-obligations/export", summary="导出报告应交/未交 Excel")
def report_obligations_export(
    batchId: str = Query(..., min_length=1),
    keyword: Optional[str] = None,
    missingOnly: bool = Query(False),
    user=Depends(require_permission(_P_REPORT_EXPORT)),
):
    return success(quality_svc.export_report_obligations(
        user, batchId, keyword=keyword or "", missing_only=missingOnly,
    ))


# ── 过程报告 ──
@router.get("/process-reports", summary="过程报告列表（教师/管理端，按数据范围）")
def report_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                reportType: Optional[str] = None, status: Optional[str] = None,
                keyword: Optional[str] = None, batchId: Optional[str] = None,
                user=Depends(require_permission(_P_REPORT_VIEW))):
    items, total = report_svc.list_reports(page, pageSize, report_type=reportType, status=status,
                                           keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/process-reports/{report_id}", summary="过程报告详情（教师/管理端，按数据范围）")
def report_detail(report_id: int, user=Depends(require_permission(_P_REPORT_VIEW))):
    return success(report_svc.get_report(report_id, user=user))


@router.post("/process-reports/{report_id}/review", summary="复核过程报告（APPROVE/RETURN）")
def report_review(report_id: int, body: dict = Body(...), user=Depends(require_permission(_P_REPORT_REVIEW))):
    b = body or {}
    return success(report_svc.review_report(
        report_id,
        b.get("action", ""),
        b.get("comment", ""),
        user=user,
        expected_version=b.get("expectedVersion", b.get("version")),
        expected_batch_id=b.get("batchId"),
        rating_level=b.get("ratingLevel"),
        summary_score=b.get("summaryScore"),
    ))


@router.post("/process-reports/export", summary="导出过程报告台账（xlsx）")
def report_export(reportType: Optional[str] = None, status: Optional[str] = None,
                  keyword: Optional[str] = None, batchId: Optional[str] = None,
                  user=Depends(require_permission(_P_REPORT_EXPORT))):
    return success(report_svc.export_reports(
        report_type=reportType, status=status, keyword=keyword, batch_id=batchId, user=user))


# ── 实习变更 ──
@router.get("/change-requests", summary="实习变更申请列表（教师/管理端，按批次+数据范围）")
def change_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                status: Optional[str] = None, keyword: Optional[str] = None,
                batchId: Optional[str] = None,
                user=Depends(require_permission(_P_CHANGE_VIEW))):
    items, total = change_svc.list_changes(
        page, pageSize, status=status, keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/change-requests/{change_id}", summary="实习变更申请详情")
def change_detail(change_id: int, user=Depends(require_permission(_P_CHANGE_VIEW))):
    return success(change_svc.get_change(change_id, user=user))


@router.post("/change-requests/{change_id}/review", summary="审批实习变更（APPROVE/REJECT）")
def change_review(change_id: int, body: dict = Body(...), user=Depends(require_permission(_P_CHANGE_REVIEW))):
    b = body or {}
    return success(change_svc.review_change(
        change_id, b.get("action", ""), b.get("comment", ""), user=user,
        expected_version=b.get("expectedVersion", b.get("version")),
        record_expected_version=b.get("recordExpectedVersion")))
