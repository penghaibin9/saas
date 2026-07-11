"""学生主档 API（阶段11）。mock 阶段敏感字段恒返回脱敏口径；tenant_id 过滤在 service 层。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import require_staff
from app.schemas.student import StudentCreateRequest, StudentUpdateRequest, StudentVoidRequest
from app.services import mock_audit_service as audit
from app.services import student_service as svc

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", summary="学生主档列表（分页 + keyword/college/major/className/status/riskLevel）")
def list_students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                  keyword: Optional[str] = None, college: Optional[str] = None,
                  major: Optional[str] = None, className: Optional[str] = None,
                  status: Optional[str] = None, riskLevel: Optional[str] = None,
                  user=Depends(require_staff)):
    items, total = svc.list_students(page, pageSize, keyword, college, major, className, status, riskLevel)
    return success(paginate(items, total, page, pageSize))


@router.get("/{student_id}", summary="学生 360 详情（主档 + 联系方式(脱敏) + 状态 + 时间线）")
def get_student(student_id: str, user=Depends(require_staff)):
    return success(svc.get_student(student_id))


@router.post("", summary="新增学生主档（mock；DB_ENABLED=true 后写 t_student_profile）")
def create_student(body: StudentCreateRequest, user=Depends(require_staff)):
    row = svc.create_student(body)
    audit.record("新增学生", method="POST", path="/api/v1/students", status_code=200,
                 target_type="student", target_id=row["id"])
    return success(row, message="建档成功")


@router.put("/{student_id}", summary="更新学生主档")
def update_student(student_id: str, body: StudentUpdateRequest, user=Depends(require_staff)):
    row = svc.update_student(student_id, body)
    audit.record("更新学生", method="PUT", path=f"/api/v1/students/{student_id}", status_code=200,
                 target_type="student", target_id=student_id)
    return success(row, message="已保存")


@router.post("/{student_id}/void", summary="作废学生主档（逻辑删除，不物理删除，原因≥5字写审计）")
def void_student(student_id: str, body: StudentVoidRequest, user=Depends(require_staff)):
    result = svc.void_student(student_id, body.reason)
    audit.record("作废学生", method="POST", path=f"/api/v1/students/{student_id}/void", status_code=200,
                 target_type="student", target_id=student_id)
    return success(result, message="已作废（逻辑删除，档案保留可追溯）")


@router.get("/{student_id}/timeline", summary="学生成长时间线")
def student_timeline(student_id: str, user=Depends(require_staff)):
    return success({"items": svc.get_timeline(student_id)})


@router.get("/{student_id}/risk-summary", summary="学生风险摘要（学业/实习/就业三维信号）")
def student_risk(student_id: str, user=Depends(require_staff)):
    return success(svc.get_risk_summary(student_id))


@router.get("/{student_id}/affairs-summary",
            summary="学生360·学工摘要（请假/奖助/违纪/宿舍/心理/家校 跨域计数；涉密明细不返回）")
def student_affairs_summary(student_id: str, user=Depends(require_staff)):
    return success(svc.get_affairs_summary(student_id))
