"""D9-S5 教务归档管理公开 Router：从 legacy academic_affairs Move Only。

归档导出继续由 academic_export_compat_router 的 ExportJob/FileObject 链持有；
归档后纠错继续由 archive_correction_router 持有。ARCHIVED 普通 unfreeze
仍由正式 service 的 immutable guard 409 fail-closed。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_svc


router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

_ARCHIVE_MANAGE = "academicAffairs.archive.manage"
_ARCHIVE_VIEW = "academicAffairs.archive.view"


class ArchiveBatchBody(BaseModel):
    termId: Optional[str] = None
    batchName: Optional[str] = None


class ArchiveConfirmBody(BaseModel):
    force: bool = Field(False, description="MISSING_ITEMS 时强制归档")


class ArchiveUnfreezeBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


@router.post("/archive/batches", summary="建归档批次（按学期，一学期一批次）")
def archive_batch_create(body: ArchiveBatchBody, user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.create_batch(user, body), message="已创建")


@router.get("/archive/batches", summary="归档批次列表")
def archive_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                    user=Depends(require_permission(_ARCHIVE_VIEW))):
    items, total = archive_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/archive/batches/{bid}", summary="归档批次详情（含9数据域物料）")
def archive_batch_detail(bid: int = Path(...), user=Depends(require_permission(_ARCHIVE_VIEW))):
    return success(archive_svc.get_batch(user, bid))


@router.post("/archive/batches/{bid}/check", summary="完整性检查（聚合9数据域）")
def archive_check(bid: int = Path(...), user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.run_check(user, bid), message="已检查")


@router.post("/archive/batches/{bid}/confirm", summary="确认归档（学期封存 ARCHIVED）")
def archive_confirm(body: ArchiveConfirmBody = ArchiveConfirmBody(), bid: int = Path(...),
                    user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.confirm_archive(user, bid, body.force), message="已归档")


@router.post("/archive/batches/{bid}/unfreeze", summary="特批解冻（正式归档后由 immutable guard 409 拒绝）")
def archive_unfreeze(body: ArchiveUnfreezeBody, bid: int = Path(...),
                     user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.unfreeze(user, bid, body.reason), message="已解冻")


@router.post("/archive/batches/{bid}/cancel", summary="取消归档批次")
def archive_cancel(bid: int = Path(...), user=Depends(require_permission(_ARCHIVE_MANAGE))):
    return success(archive_svc.cancel_batch(user, bid), message="已取消")


@router.get("/archive/precheck", summary="归档缺失提醒：9域实时预检查（不落库）")
def archive_precheck(termId: Optional[str] = None, user=Depends(require_permission(_ARCHIVE_VIEW))):
    return success(archive_svc.precheck(user, termId))


@router.get("/archive/batches/{bid}/download-log", summary="归档下载记录查询")
def archive_download_log(bid: int = Path(...), user=Depends(require_permission(_ARCHIVE_VIEW))):
    return success(archive_svc.list_download_log(user, bid))
