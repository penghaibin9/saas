"""D8-S2 成绩读侧 Move Only Router。

只迁出 legacy 大 Router 仍持有的学生成绩单、挂科清单、成绩分析、成绩异常与成绩审计读取入口。
成绩单/分析正式导出继续由 academic_export_compat_router 的 ExportJob owner 持有；成绩更正、复查、认定
等写链继续留在既有 owner。服务、权限、分页和响应语义全部复用 legacy/canonical，不新增成绩事实写入口。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.core.security import require_staff
from app.modules.academic_affairs.routers import academic_affairs as legacy

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-成绩读侧"])

grade_svc = legacy.grade_svc


@router.get("/students/{studentId}/transcript", summary="学生成绩单（读侧）")
def grade_transcript(
    studentId: int = Path(...),
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    return success(grade_svc.transcript(studentId, user))


@router.get("/grade-views/fail-list", summary="挂科清单（读侧下钻）")
def grade_fail_list(
    term: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    items, total = grade_svc.fail_list(user, term, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/grade-views/analysis", summary="成绩分析（分数段+及格率+优秀率+平均分，可按课程/班级分组）")
def grade_analysis(
    term: Optional[str] = None,
    dimension: Optional[str] = None,
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    return success(grade_svc.grade_analysis(user, term, dimension))


@router.get("/grade-views/exception-list", summary="成绩异常清单（缺考/缓考/免修标记学生汇总，读侧下钻）")
def grade_exception_list(
    term: Optional[str] = None,
    exceptionFlag: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_staff),
):
    items, total = grade_svc.exception_list(user, term, exceptionFlag, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/grade-views/audit", summary="成绩操作审计（读侧，AA_GRADE_*；教务处/学院查全量，教师自查本人）")
def grade_audit_list(
    bizType: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission("academicAffairs.grade.view")),
):
    items, total = grade_svc.list_grade_audit(user, bizType, page, pageSize)
    return success(paginate(items, total, page, pageSize))
