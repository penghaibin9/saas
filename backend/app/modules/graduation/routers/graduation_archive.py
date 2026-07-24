"""毕业设计中心 · 毕设归档 API（/api/v1/graduation/gd-archives/*）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.core.permissions import require_permission
from app.modules.graduation.schemas.graduation_archive import ArchiveFileRequest, ArchiveRejectRequest
from app.services import audit_log
from app.modules.graduation.services import graduation_archive_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-毕设归档"])


@router.get("/gd-archives/stats", summary="归档统计（归档率）")
def gd_archive_stats(batchId: int | None = Query(default=None, ge=1),
                     user=Depends(get_current_user)):
    return success(svc.archive_stats(batch_id=batchId))


@router.post("/gd-archives/batch-generate/preview", summary="批量生成提交预检查（不写状态）")
def gd_archive_batch_generate_preview(batchId: int | None = Query(default=None, ge=1),
                                      user=Depends(get_current_user)):
    return success(svc.preview_batch_generate(batch_id=batchId))


@router.post("/gd-archives/batch-generate", summary="批量归档·对材料齐全学生一键生成+提交")
def gd_archive_batch_generate(batchId: int | None = Query(default=None, ge=1),
                              user=Depends(get_current_user)):
    result = svc.batch_generate_submit(batch_id=batchId)
    audit_log.record("批量生成提交归档", "graduation-archive:batch-generate", detail=result)
    return success(result, message=f"已提交 {result['submitted']}，缺材料跳过 {result['skipped']}")


@router.post("/gd-archives/batch-file/preview", summary="批量核验备案预检查（不写状态）")
def gd_archive_batch_file_preview(batchId: int | None = Query(default=None, ge=1),
                                  user=Depends(get_current_user)):
    return success(svc.preview_batch_file(batch_id=batchId))


@router.post("/gd-archives/batch-file", summary="批量归档·一键核验备案全部已提交")
def gd_archive_batch_file(batchId: int | None = Query(default=None, ge=1),
                          body: dict = Body(default={}),
                          user=Depends(get_current_user)):
    result = svc.batch_file((body or {}).get("archiveBatchNo"), batch_id=batchId)
    audit_log.record("批量核验归档", "graduation-archive:batch-file", detail=result)
    return success(result, message=f"已备案 {result['filed']} 份")


@router.post("/gd-archives/export", summary="导出归档台账 Excel（写审计）")
def gd_archive_export(status: Optional[str] = None, keyword: Optional[str] = None,
                      batchId: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_archives_xlsx(status=status, keyword=keyword, batch_id=batchId)
    audit_log.record("导出毕设归档台账", "graduation-archive:export",
                     detail={"rowCount": data["rowCount"], "batchId": batchId, "status": status})
    return success(data)


@router.get("/gd-archives", summary="归档列表（分页+筛选）")
def gd_archives(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                keyword: Optional[str] = None, status: Optional[str] = None,
                batchId: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_archives(page, pageSize, keyword=keyword, status=status, batch_id=batchId)
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-archives/{gd_student_id}", summary="按学生查归档记录（不存在时返回待生成态，不落库）")
def gd_archive_detail(gd_student_id: str, user=Depends(get_current_user)):
    return success(svc.get_archive(gd_student_id))


@router.post("/gd-archives/{gd_student_id}/generate", summary="生成归档清单（自动核验必备材料）")
def gd_archive_generate(gd_student_id: str, user=Depends(get_current_user)):
    result = svc.generate_archive(gd_student_id)
    audit_log.record("生成归档清单", f"graduation-archive:{gd_student_id}")
    return success(result, message="已生成")


@router.post("/gd-archives/{gd_student_id}/submit", summary="提交归档（须无缺失材料）")
def gd_archive_submit(gd_student_id: str, user=Depends(require_permission("graduationDesign.archive.submit"))):
    result = svc.submit_archive(gd_student_id)
    audit_log.record("提交归档", f"graduation-archive:{gd_student_id}")
    return success(result, message="已提交")


@router.post("/gd-archives/{gd_student_id}/file", summary="核验归档（已提交→已备案）")
def gd_archive_file(gd_student_id: str, body: ArchiveFileRequest, user=Depends(get_current_user)):
    result = svc.verify_and_file(gd_student_id, body.archiveBatchNo)
    audit_log.record("核验归档", f"graduation-archive:{gd_student_id}")
    return success(result, message="已归档")


@router.post("/gd-archives/{gd_student_id}/reject", summary="驳回归档（原因≥5字）")
def gd_archive_reject(gd_student_id: str, body: ArchiveRejectRequest, user=Depends(get_current_user)):
    result = svc.reject_archive(gd_student_id, body.reason)
    audit_log.record("驳回归档", f"graduation-archive:{gd_student_id}", detail={"reason": body.reason})
    return success(result, message="已驳回")
