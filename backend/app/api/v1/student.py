"""学生主档 API（阶段11）。mock 阶段敏感字段恒返回脱敏口径；tenant_id 过滤在 service 层。

数据范围（SEC 口径，2026-07-17 收敛）：本目录是跨域公共学生选择器的后端，
仅对具有明确范围语义的学工侧角色按 StudentAffairsSecurityContext 收敛：
辅导员/班主任(CLASS)、学院管理员(COLLEGE)、心理教师(PSY 授权学生)；未配 scope = fail-closed 空。
管理类角色(TENANT_ALL)不收敛；毕设/实习/就业/宿管等其他域角色沿用全租户目录语义
（各域业务端点已有本域范围校验，收敛口径见「上线前必做清单-总闸门」登记）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.affairs_security import no_data_scope, student_directory_scope
from app.core.response import paginate, success
from app.core.security import require_staff
from app.schemas.student import StudentCreateRequest, StudentUpdateRequest, StudentVoidRequest
from app.services import mock_audit_service as audit
from app.services import student_service as svc

router = APIRouter(prefix="/students", tags=["students"])


def _check_target_scope(student_id: str, user) -> None:
    """详情/写操作目标学生范围校验；越租户仍由 service 报 not_found（不泄露存在性）。"""
    class_ids, student_ids = student_directory_scope(user)
    if class_ids is None and student_ids is None:
        return
    from app.services.db_service import _tid, session
    from app.models import StudentProfile
    try:
        sid = int(student_id)
    except (TypeError, ValueError):
        return  # 非法 id 交给 service 报 not_found
    with session() as db:
        s = db.get(StudentProfile, sid)
        if s is None or getattr(s, "is_deleted", False) or s.tenant_id != _tid():
            return  # 不存在/越租户 → service 统一 not_found
        if student_ids is not None:
            if s.id in student_ids:
                return
        elif s.class_id is not None and s.class_id in class_ids:
            return
    raise no_data_scope("该学生不在您的数据范围内")


@router.get("", summary="学生主档列表（分页 + keyword/college/major/className/status/riskLevel；按角色数据范围收敛）")
def list_students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                  keyword: Optional[str] = None, college: Optional[str] = None,
                  major: Optional[str] = None, className: Optional[str] = None,
                  status: Optional[str] = None, riskLevel: Optional[str] = None,
                  user=Depends(require_staff)):
    class_ids, student_ids = student_directory_scope(user)
    items, total = svc.list_students(page, pageSize, keyword, college, major, className, status, riskLevel,
                                     class_ids=class_ids, student_ids=student_ids)
    return success(paginate(items, total, page, pageSize))


@router.get("/{student_id}", summary="学生 360 详情（主档 + 联系方式(脱敏) + 状态 + 时间线）")
def get_student(student_id: str, user=Depends(require_staff)):
    _check_target_scope(student_id, user)
    return success(svc.get_student(student_id))


@router.post("", summary="新增学生主档（mock；DB_ENABLED=true 后写 t_student_profile）")
def create_student(body: StudentCreateRequest, user=Depends(require_staff)):
    row = svc.create_student(body)
    audit.record("新增学生", method="POST", path="/api/v1/students", status_code=200,
                 target_type="student", target_id=row["id"])
    return success(row, message="建档成功")


@router.put("/{student_id}", summary="更新学生主档")
def update_student(student_id: str, body: StudentUpdateRequest, user=Depends(require_staff)):
    _check_target_scope(student_id, user)
    row = svc.update_student(student_id, body)
    audit.record("更新学生", method="PUT", path=f"/api/v1/students/{student_id}", status_code=200,
                 target_type="student", target_id=student_id)
    return success(row, message="已保存")


@router.post("/{student_id}/void", summary="作废学生主档（逻辑删除，不物理删除，原因≥5字写审计）")
def void_student(student_id: str, body: StudentVoidRequest, user=Depends(require_staff)):
    _check_target_scope(student_id, user)
    result = svc.void_student(student_id, body.reason)
    audit.record("作废学生", method="POST", path=f"/api/v1/students/{student_id}/void", status_code=200,
                 target_type="student", target_id=student_id)
    return success(result, message="已作废（逻辑删除，档案保留可追溯）")


@router.get("/{student_id}/timeline", summary="学生成长时间线")
def student_timeline(student_id: str, user=Depends(require_staff)):
    _check_target_scope(student_id, user)
    return success({"items": svc.get_timeline(student_id)})


@router.get("/{student_id}/risk-summary", summary="学生风险摘要（学业/实习/就业三维信号）")
def student_risk(student_id: str, user=Depends(require_staff)):
    _check_target_scope(student_id, user)
    return success(svc.get_risk_summary(student_id))
