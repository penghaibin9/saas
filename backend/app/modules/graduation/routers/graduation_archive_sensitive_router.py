"""归档单生接口的批次强校验与单一域审计入口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_archive import ArchiveFileRequest, ArchiveRejectRequest
from app.modules.graduation.services import graduation_archive_service as svc
from app.modules.graduation.services.graduation_batch_context import load_student_in_batch, require_batch_id
from app.services.db_service import session

router = APIRouter(prefix="/graduation", tags=["毕业设计-归档批次安全"])


def _guard(student_id, batch_id, *, lock=False):
    with session() as db:
        load_student_in_batch(db, student_id, batch_id, for_update=lock)


@router.get("/gd-archives/stats")
def stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(svc.archive_stats(batch_id=require_batch_id(batchId)))


@router.get("/gd-archives")
def list_rows(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None, status: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    items, total = svc.list_archives(page, pageSize, keyword=keyword, status=status, batch_id=batchId)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-archives/export")
def export_rows(
    status: Optional[str] = None, keyword: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(svc.export_archives_xlsx(status=status, keyword=keyword, batch_id=batchId))


@router.get("/gd-archives/{gd_student_id}")
def detail(
    gd_student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId)
    return success(svc.get_archive(gd_student_id))


@router.post("/gd-archives/{gd_student_id}/generate")
def generate(
    gd_student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(svc.generate_archive(gd_student_id), message="已生成")


@router.post("/gd-archives/{gd_student_id}/submit")
def submit(
    gd_student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(svc.submit_archive(gd_student_id), message="已提交")


@router.post("/gd-archives/{gd_student_id}/file")
def file_record(
    gd_student_id: str, body: ArchiveFileRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(svc.verify_and_file(gd_student_id, body.archiveBatchNo), message="已归档")


@router.post("/gd-archives/{gd_student_id}/reject")
def reject(
    gd_student_id: str, body: ArchiveRejectRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(svc.reject_archive(gd_student_id, body.reason), message="已驳回")
