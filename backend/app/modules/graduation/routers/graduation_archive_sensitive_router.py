"""归档接口的批次强校验、签名预览和单一域审计入口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.exceptions import AppException
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_archive import ArchiveFileRequest, ArchiveRejectRequest
from app.modules.graduation.services import graduation_archive_service as svc
from app.modules.graduation.services import graduation_material_center_service as material_center
from app.modules.graduation.services.graduation_batch_context import load_student_in_batch, require_batch_id
from app.services.db_service import session

router = APIRouter(prefix="/graduation", tags=["毕业设计-归档批次安全"])

# 任务书安全 Router 不设 prefix，由此挂入同一 /graduation 前缀并优先于旧 Router。
from app.modules.graduation.routers import graduation_taskbook_sensitive_router
router.include_router(graduation_taskbook_sensitive_router.router)


def _guard(student_id, batch_id, *, lock=False):
    with session() as db:
        load_student_in_batch(db, student_id, batch_id, for_update=lock)


def _preview_token(body: dict | None) -> str:
    token = str((body or {}).get("previewToken") or "").strip()
    if not token:
        raise AppException("VALIDATION_ERROR", "执行前必须先完成归档预览")
    return token


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


# 动态 /{gd_student_id} 之前注册批量固定路径，避免被误识别为学生 ID。
@router.post("/gd-archives/batch-generate/preview")
def batch_generate_preview(
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(svc.preview_batch_generate(batch_id=require_batch_id(batchId)))


@router.post("/gd-archives/batch-generate")
def batch_generate(
    batchId: int = Query(..., ge=1), body: dict = Body(...),
    user=Depends(get_current_user),
):
    result = svc.batch_generate_submit(
        batch_id=require_batch_id(batchId), preview_token=_preview_token(body),
    )
    return success(result, message=f"已提交 {result['submitted']}，跳过 {result['skipped']}")


@router.post("/gd-archives/batch-file/preview")
def batch_file_preview(
    batchId: int = Query(..., ge=1), body: dict = Body(default={}),
    user=Depends(get_current_user),
):
    return success(svc.preview_batch_file(
        batch_id=require_batch_id(batchId), archive_batch_no=(body or {}).get("archiveBatchNo"),
    ))


@router.post("/gd-archives/batch-file")
def batch_file(
    batchId: int = Query(..., ge=1), body: dict = Body(...),
    user=Depends(get_current_user),
):
    archive_no = str((body or {}).get("archiveBatchNo") or "").strip() or None
    result = material_center.batch_file(
        archive_no, require_batch_id(batchId), _preview_token(body), user,
    )
    return success(result, message=f"已备案 {result['filed']} 份")


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
    return success(material_center.file_archive(int(gd_student_id), body.archiveBatchNo, user), message="已归档并冻结真实版本清单")


@router.post("/gd-archives/{gd_student_id}/reject")
def reject(
    gd_student_id: str, body: ArchiveRejectRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(svc.reject_archive(gd_student_id, body.reason), message="已驳回")
