"""毕业设计中心 · 任务书 API（/api/v1/graduation/gd-taskbooks/*）。

独立 router；静态子路由（stats/export）在 /{gd_student_id} 之前声明。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.graduation_taskbook import TaskBookChangeRequest, TaskBookIssue
from app.services import audit_log
from app.services import graduation_taskbook_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-任务书"])


@router.get("/gd-taskbooks/stats", summary="任务书统计")
def gd_taskbook_stats(user=Depends(get_current_user)):
    return success(svc.taskbook_stats())


@router.post("/gd-taskbooks/export", summary="导出任务书台账 Excel（写审计）")
def gd_taskbook_export(status: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_taskbooks_xlsx(status=status)
    audit_log.record("导出任务书台账", "graduation-taskbook:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/gd-taskbooks", summary="任务书列表（分页+筛选）")
def gd_taskbooks(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                keyword: Optional[str] = None, status: Optional[str] = None,
                user=Depends(get_current_user)):
    items, total = svc.list_taskbooks(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-taskbooks/{gd_student_id}", summary="按学生查任务书（不存在返回 exists=false）")
def gd_taskbook_detail(gd_student_id: str, user=Depends(get_current_user)):
    return success(svc.get_taskbook(gd_student_id))


@router.post("/gd-taskbooks/{gd_student_id}/issue", summary="下达任务书（须已分配导师，且尚无任务书）")
def gd_taskbook_issue(gd_student_id: str, body: TaskBookIssue, user=Depends(get_current_user)):
    result = svc.issue_taskbook(gd_student_id, body.model_dump())
    audit_log.record("下达任务书", f"graduation-taskbook:{gd_student_id}")
    return success(result, message="已下达，待学生确认")


@router.post("/gd-taskbooks/{gd_student_id}/confirm", summary="学生确认任务书")
def gd_taskbook_confirm(gd_student_id: str, user=Depends(get_current_user)):
    result = svc.confirm_taskbook(gd_student_id)
    audit_log.record("确认任务书", f"graduation-taskbook:{gd_student_id}")
    return success(result, message="已确认")


@router.post("/gd-taskbooks/{gd_student_id}/change", summary="变更任务书（原因≥5字，仅已确认可变更）")
def gd_taskbook_change(gd_student_id: str, body: TaskBookChangeRequest, user=Depends(get_current_user)):
    result = svc.change_taskbook(gd_student_id, body.model_dump())
    audit_log.record("变更任务书", f"graduation-taskbook:{gd_student_id}", detail={"reason": body.reason})
    return success(result, message="已提交变更，待学生重新确认")
