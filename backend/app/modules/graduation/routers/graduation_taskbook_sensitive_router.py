"""任务书学校端批次安全接口；由 graduation_archive_sensitive_router 挂入 /graduation。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_taskbook import TaskBookChangeRequest, TaskBookIssue
from app.modules.graduation.services import graduation_taskbook_service as svc
from app.modules.graduation.services.graduation_batch_context import load_student_in_batch, require_batch_id
from app.modules.graduation.services.graduation_taskbook_consistency import install_taskbook_consistency
from app.services.db_service import session

install_taskbook_consistency()
router = APIRouter(tags=["毕业设计-任务书批次安全"])

from app.modules.graduation.routers import graduation_process_sensitive_router
router.include_router(graduation_process_sensitive_router.router)


def _guard(student_id, batch_id, *, lock=False):
    with session() as db:
        load_student_in_batch(db, student_id, batch_id, for_update=lock)


@router.get("/gd-taskbooks/stats")
def stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(svc.taskbook_stats(batch_id=require_batch_id(batchId)))


@router.get("/gd-taskbooks")
def list_rows(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None, status: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    items, total = svc.list_taskbooks(
        page, pageSize, keyword=keyword, status=status, batch_id=batchId,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-taskbooks/export")
def export_rows(
    status: Optional[str] = None, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(svc.export_taskbooks_xlsx(status=status, batch_id=batchId))


@router.get("/gd-taskbooks/{gd_student_id}")
def detail(
    gd_student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId)
    return success(svc.get_taskbook(gd_student_id))


@router.post("/gd-taskbooks/{gd_student_id}/issue")
def issue(
    gd_student_id: str, body: TaskBookIssue,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(svc.issue_taskbook(gd_student_id, body.model_dump()), message="已下达，待学生确认")


@router.post("/gd-taskbooks/{gd_student_id}/confirm")
def confirm(
    gd_student_id: str, body: dict = Body(default={}),
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(svc.confirm_taskbook(
        gd_student_id, proxy_reason=(body or {}).get("proxyReason"),
    ), message="已确认")


@router.post("/gd-taskbooks/{gd_student_id}/change")
def change(
    gd_student_id: str, body: TaskBookChangeRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(svc.change_taskbook(gd_student_id, body.model_dump()), message="已提交变更，待学生重新确认")


@router.post("/gd-taskbooks/{gd_student_id}/export-pdf", summary="导出毕业设计任务书正式 PDF")
def export_pdf(
    gd_student_id: str, templateId: Optional[str] = Query(None),
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId)
    return success(svc.export_taskbook_pdf(gd_student_id, template_id=templateId))
