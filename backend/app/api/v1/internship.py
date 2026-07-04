"""岗位实习域 API（/api/v1/internship/*）。真实走库；写操作落审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.internship import ExceptionHandleRequest, ReportReviewRequest
from app.services import audit_log
from app.services import internship_service as svc

router = APIRouter(prefix="/internship", tags=["岗位实习"])


@router.get("/dashboard", summary="实习中心看板")
def dashboard(user=Depends(get_current_user)):
    return success(svc.get_dashboard_summary())


@router.get("/students", summary="实习学生列表（分页+筛选）")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             status: Optional[str] = None, riskLevel: Optional[str] = None,
             user=Depends(get_current_user)):
    items, total = svc.list_internship_students(page, pageSize, keyword=keyword, class_id=classId,
                                                status=status, risk_level=riskLevel)
    return success(paginate(items, total, page, pageSize))


@router.get("/students/{record_id}", summary="实习学生详情（含打卡/周报/风险/留痕）")
def student_detail(record_id: str, user=Depends(get_current_user)):
    return success(svc.get_internship_student_detail(record_id))


@router.get("/exceptions", summary="打卡异常列表")
def exceptions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               type: Optional[str] = None, status: Optional[str] = None,
               keyword: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_attendance_exceptions(page, pageSize, type=type, status=status,
                                                  keyword=keyword)
    return success(paginate(items, total, page, pageSize))


@router.get("/exceptions/{exception_id}", summary="打卡异常详情（含处理留痕）")
def exception_detail(exception_id: str, user=Depends(get_current_user)):
    return success(svc.get_exception_detail(exception_id))


@router.post("/exceptions/{exception_id}/handle", summary="处理打卡异常（合理/异常/转风险，意见≥5字）")
def handle_exception(exception_id: str, body: ExceptionHandleRequest,
                     user=Depends(get_current_user)):
    result = svc.handle_attendance_exception(exception_id, body.action, body.comment)
    audit_log.record("处理打卡异常", f"internship-exception:{exception_id}",
                     detail={"action": body.action})
    return success(result, message="已处理")


@router.get("/reports", summary="周报批阅列表")
def reports(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            status: Optional[str] = None, keyword: Optional[str] = None,
            user=Depends(get_current_user)):
    items, total = svc.list_weekly_reports(page, pageSize, status=status, keyword=keyword)
    return success(paginate(items, total, page, pageSize))


@router.get("/reports/{report_id}", summary="周报详情（含批阅留痕）")
def report_detail(report_id: str, user=Depends(get_current_user)):
    return success(svc.get_weekly_report_detail(report_id))


@router.post("/reports/{report_id}/review", summary="批阅周报（通过/退回，退回原因≥5字）")
def review_report(report_id: str, body: ReportReviewRequest, user=Depends(get_current_user)):
    result = svc.review_weekly_report(report_id, body.action, body.comment)
    audit_log.record("批阅周报", f"internship-report:{report_id}", detail={"action": body.action})
    return success(result, message="批阅完成")


@router.get("/risks", summary="实习风险学生列表")
def risks(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
          level: Optional[str] = None, status: Optional[str] = None,
          user=Depends(get_current_user)):
    items, total = svc.list_risk_students(page, pageSize, level=level, status=status)
    return success(paginate(items, total, page, pageSize))
