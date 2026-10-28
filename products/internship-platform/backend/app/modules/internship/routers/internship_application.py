"""Staff endpoints for formal internship application review.

权限（P3）：查询 internship.application.view，审核 internship.application.review
（校管/学院负责人/指导教师均可，数据范围由 service 收敛）。
"""
from __future__ import annotations

from typing import Optional

from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_application_service as svc
from app.services import audit_log

router = APIRouter(prefix="/internship/applications", tags=["岗位实习-正式申请"])

_P_VIEW = "internship.application.view"
_P_REVIEW = "internship.application.review"


def application_filters(
    academicYear: Optional[str] = Query(None, max_length=20),
    grade: Optional[str] = Query(None, max_length=20),
    collegeId: Optional[str] = Query(None, pattern=r"^[1-9][0-9]{0,18}$"),
    majorId: Optional[str] = Query(None, pattern=r"^[1-9][0-9]{0,18}$"),
    classId: Optional[str] = Query(None, pattern=r"^[1-9][0-9]{0,18}$"),
    studentName: Optional[str] = Query(None, max_length=100),
    studentNo: Optional[str] = Query(None, max_length=100),
    exemptionType: Optional[str] = Query(None, max_length=30),
):
    return dict(academic_year=academicYear, grade=grade, college_id=collegeId,
                major_id=majorId, class_id=classId, student_name=studentName,
                student_no=studentNo, exemption_type=exemptionType)


@router.get("")
def applications(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                 status: Optional[str] = None, applicationType: Optional[str] = None,
                 keyword: Optional[str] = None, batchId: Optional[str] = None,
                 filters: dict = Depends(application_filters),
                 user=Depends(require_permission(_P_VIEW))):
    items, total = svc.list_applications(
        page, pageSize, status, applicationType, keyword, batch_id=batchId, user=user, **filters)
    return success(paginate(items, total, page, pageSize))


@router.get("/filter-options")
def filter_options(batchId: str = Query(..., min_length=1),
                   user=Depends(require_permission(_P_VIEW))):
    return success(svc.application_filter_options(batch_id=batchId, user=user))


@router.get("/summary")
def application_summary(batchId: str = Query(..., min_length=1),
                        user=Depends(require_permission(_P_VIEW))):
    return success(svc.application_summary(batch_id=batchId, user=user))


@router.get("/students")
def application_students(state: str = Query(..., min_length=1),
                         page: int = Query(1, ge=1),
                         pageSize: int = Query(20, ge=1, le=200),
                         keyword: Optional[str] = None,
                         batchId: str = Query(..., min_length=1),
                         user=Depends(require_permission(_P_VIEW))):
    items, total = svc.list_application_students(
        page, pageSize, state, batch_id=batchId, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))

@router.get("/export.xlsx", summary="按当前筛选条件导出完整实习申请审核台账")
def applications_export(
    status: Optional[str] = None,
    applicationType: Optional[str] = None,
    keyword: Optional[str] = None,
    batchId: Optional[str] = None,
    filters: dict = Depends(application_filters),
    user=Depends(require_permission(_P_VIEW)),
):
    payload, filename, _row_count = svc.export_applications(
        status=status,
        application_type=applicationType,
        keyword=keyword,
        batch_id=batchId,
        user=user,
        **filters,
    )
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
                 "Cache-Control": "no-store"},
    )


@router.get("/{application_id}")
def application_detail(application_id: str, user=Depends(require_permission(_P_VIEW))):
    return success(svc.get_application(application_id, user))


@router.post("/{application_id}/review")
def application_review(application_id: str, body: dict = Body(...), user=Depends(require_permission(_P_REVIEW))):
    b = body or {}
    result = svc.review_application(
        application_id, b.get("action", ""), b.get("comment", ""), user,
        expected_version=b.get("expectedVersion", b.get("version")),
        record_expected_version=b.get("recordExpectedVersion"),
        expected_batch_id=b.get("batchId"))
    audit_log.record("审核实习申请", f"internship-application:{application_id}",
                     detail={"action": b.get("action", "")})
    return success(result, message="申请已处理")
