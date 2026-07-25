"""学生主档 API。

两种语义：
1) 主档管理：student.profile.view / manage，未知角色 fail-closed（空范围）。
2) 公共选择器：?mode=picker，仅最小字段，且必须按数据范围过滤，无写能力。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.affairs_security import no_data_scope, student_directory_scope
from app.core.exceptions import AppException
from app.core.permissions import has_permission, require_permission
from app.core.response import paginate, success
from app.core.security import require_staff
from app.schemas.student import StudentCreateRequest, StudentUpdateRequest, StudentVoidRequest
from app.services import mock_audit_service as audit
from app.services import student_service as svc

router = APIRouter(prefix="/students", tags=["students"])

_PICKER_PERMS = (
    "student.profile.view",
    "studentAffairs.student.view",
    "campusService.student.view",
    "internship.student.view",
    "graduationDesign.view",
    "academicAffairs.roster.view",
)


def _can_pick_students(user) -> bool:
    return has_permission(user, "*") or any(has_permission(user, p) for p in _PICKER_PERMS)


def _can_view_profile(user) -> bool:
    return has_permission(user, "*") or has_permission(user, "student.profile.view")


def _check_target_scope(student_id: str, user) -> None:
    """详情/写操作目标学生范围校验；越租户仍由 service 报 not_found。"""
    class_ids, student_ids = student_directory_scope(user)
    if class_ids is None and student_ids is None:
        return
    # 空集合：明确无范围
    if student_ids is not None and len(student_ids) == 0:
        raise no_data_scope("该学生不在您的数据范围内")
    if class_ids is not None and len(class_ids) == 0 and student_ids is None:
        raise no_data_scope("该学生不在您的数据范围内")
    from sqlalchemy import select

    from app.models import StudentProfile
    from app.services.db_service import _tid, session
    try:
        sid = int(student_id)
    except (TypeError, ValueError):
        return
    with session() as db:
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.id == sid, StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False))).first()
        if s is None:
            return
        if student_ids is not None:
            if s.id in student_ids:
                return
        elif s.class_id is not None and s.class_id in class_ids:
            return
    raise no_data_scope("该学生不在您的数据范围内")


def _to_picker_item(row: dict) -> dict:
    return {
        "id": row.get("id") or row.get("studentId"),
        "studentId": row.get("id") or row.get("studentId"),
        "studentNo": row.get("studentNo"),
        "realName": row.get("realName") or row.get("name"),
        "className": row.get("className"),
        "collegeName": row.get("collegeName"),
        "majorName": row.get("majorName"),
        "status": row.get("status") or row.get("studentStatus"),
    }


@router.get("", summary="学生列表（主档或选择器）")
def list_students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                  keyword: Optional[str] = None, college: Optional[str] = None,
                  major: Optional[str] = None, className: Optional[str] = None,
                  status: Optional[str] = None, riskLevel: Optional[str] = None,
                  mode: Optional[str] = Query(None, description="picker=最小字段选择器"),
                  user=Depends(require_staff)):
    is_picker = (mode or "").strip().lower() == "picker"
    if is_picker:
        if not _can_pick_students(user):
            raise AppException("NO_PERMISSION", "无权检索学生目录")
    elif not _can_view_profile(user) and not _can_pick_students(user):
        raise AppException("NO_PERMISSION", "无权查看学生主档")
    class_ids, student_ids = student_directory_scope(user)
    items, total = svc.list_students(page, pageSize, keyword, college, major, className, status, riskLevel,
                                     class_ids=class_ids, student_ids=student_ids)
    if is_picker or not _can_view_profile(user):
        items = [_to_picker_item(x) for x in items]
    return success(paginate(items, total, page, pageSize))


@router.get("/{student_id}", summary="学生 360 详情")
def get_student(student_id: str, mode: Optional[str] = Query(None), user=Depends(require_staff)):
    is_picker = (mode or "").strip().lower() == "picker"
    if is_picker:
        if not _can_pick_students(user):
            raise AppException("NO_PERMISSION", "无权检索学生目录")
    elif not _can_view_profile(user):
        # 无主档查看权：仅返回最小字段（若有域内学生查看权）
        if not _can_pick_students(user):
            raise AppException("NO_PERMISSION", "无权查看学生主档")
        is_picker = True
    _check_target_scope(student_id, user)
    row = svc.get_student(student_id)
    return success(_to_picker_item(row) if is_picker else row)


@router.post("", summary="新增学生主档",
             dependencies=[Depends(require_permission("student.profile.manage"))])
def create_student(body: StudentCreateRequest, user=Depends(require_staff)):
    row = svc.create_student(body)
    audit.record("新增学生" if not row.get("restored") else "复活学生",
                 method="POST", path="/api/v1/students", status_code=200,
                 target_type="student", target_id=row["id"],
                 detail={"restored": bool(row.get("restored"))})
    msg = "已复活原学号主档" if row.get("restored") else "建档成功"
    return success(row, message=msg)


@router.put("/{student_id}", summary="更新学生主档",
            dependencies=[Depends(require_permission("student.profile.manage"))])
def update_student(student_id: str, body: StudentUpdateRequest, user=Depends(require_staff)):
    _check_target_scope(student_id, user)
    row = svc.update_student(student_id, body)
    audit.record("更新学生", method="PUT", path=f"/api/v1/students/{student_id}", status_code=200,
                 target_type="student", target_id=student_id)
    return success(row, message="已保存")


@router.post("/{student_id}/void", summary="作废学生主档",
             dependencies=[Depends(require_permission("student.profile.manage"))])
def void_student(student_id: str, body: StudentVoidRequest, user=Depends(require_staff)):
    _check_target_scope(student_id, user)
    # DB 模式：作废与高危审计同事务；mock 模式仍走 record_critical
    from app.db.session import db_enabled
    result = svc.void_student(student_id, body.reason)
    if not db_enabled():
        audit.record_critical(
            "作废学生", method="POST", path=f"/api/v1/students/{student_id}/void",
            status_code=200, target_type="student", target_id=student_id,
            detail={"reason": body.reason})
    return success(result, message="已作废（逻辑删除，档案保留可追溯；同号仅可复活）")


@router.get("/{student_id}/timeline", summary="学生成长时间线")
def student_timeline(student_id: str, user=Depends(require_staff)):
    if not _can_view_profile(user):
        raise AppException("NO_PERMISSION", "无权查看学生主档")
    _check_target_scope(student_id, user)
    return success({"items": svc.get_timeline(student_id)})


@router.get("/{student_id}/risk-summary", summary="学生风险摘要")
def student_risk(student_id: str, user=Depends(require_staff)):
    if not _can_view_profile(user):
        raise AppException("NO_PERMISSION", "无权查看学生主档")
    _check_target_scope(student_id, user)
    return success(svc.get_risk_summary(student_id))
