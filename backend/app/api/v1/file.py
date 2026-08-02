"""文件上传会话与扫描运维 API；普通上传权威合同为 ``POST /files``。"""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.file_contract import metadata_contract
from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.core.rbac09_permission_bundles import (
    FILE_GOVERNANCE_VIEW,
    FILE_SCAN_RETRY,
    require_permission_compat,
)
from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log
from app.services.file_scan_service import health_snapshot, retry_file_scan

router = APIRouter(tags=["S9·文件上传会话与扫描"])
placeholder_router = APIRouter(tags=["S9·文件上传占位（非生产）"])
MAX_SIZE = 50 * 1024 * 1024
ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "png", "jpg", "jpeg", "gif", "zip", "txt", "csv"}


class UploadSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fileName: str = Field(..., min_length=1, max_length=300)
    sizeBytes: int = Field(..., gt=0)
    sha256: str | None = Field(None, max_length=64)
    bizType: str = Field("ATTACHMENT", min_length=1, max_length=80)
    bizId: str | None = Field(None, max_length=100)
    clientType: str = Field("ADMIN_PC", min_length=1, max_length=40)
    idempotencyKey: str = Field(..., min_length=8, max_length=100)


class UploadSessionComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    etag: str | None = Field(None, max_length=128)


@placeholder_router.post("/upload-placeholder", summary="文件上传占位（仅非生产；不落盘）")
async def upload_placeholder(file: UploadFile = File(...), user=Depends(get_current_user)):
    if settings.is_prod:
        raise not_found("接口不存在")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_EXT:
        raise AppException("FILE_TYPE_NOT_ALLOWED", f"文件类型不允许：.{ext or '未知'}", details={"allowed": sorted(ALLOWED_EXT)})
    sha, size = hashlib.sha256(), 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_SIZE:
            raise AppException("FILE_TOO_LARGE", "文件超过 50MB 上限")
        sha.update(chunk)
    file_id = f"file-{uuid.uuid4().hex[:20]}"
    meta = {
        "fileId": file_id,
        "fileName": file.filename,
        "size": size,
        "mimeType": file.content_type,
        "hash": sha.hexdigest(),
        "notice": "非生产占位：未落盘；请改用正式文件上传接口",
    }
    audit_log.record("FILE_UPLOAD", f"file:{file_id}", {"fileName": file.filename, "size": size, "placeholder": True})
    return success(meta)


def _session_reservation_key(session_id: str) -> str:
    return f"cos-session:{str(session_id).strip()}"


@router.post("/upload-sessions", summary="创建 COS 精确对象直传会话")
def create_upload_session(body: UploadSessionCreate, user=Depends(get_current_user)):
    from app.services.file_storage_quota_reservation_service import _module_from_biz, reserve_quota
    from app.services.storage.production import (
        abandon_upload_session as abandon_session,
        create_upload_session as create_session,
    )

    result = create_session(
        filename=body.fileName,
        size_bytes=body.sizeBytes,
        sha256=body.sha256,
        biz_type=body.bizType,
        biz_id=body.bizId,
        client_type=body.clientType,
        idempotency_key=body.idempotencyKey,
        user=user,
    )
    session_id = str(result.get("sessionId") or "")
    if result.get("status") != "COMPLETED":
        try:
            reserve_quota(
                reservation_key=_session_reservation_key(session_id),
                source_type="COS_UPLOAD_SESSION",
                source_id=session_id,
                size_bytes=body.sizeBytes,
                module_code=_module_from_biz(body.bizType),
                ttl_seconds=30 * 60,
            )
        except Exception:
            try:
                abandon_session(session_id, user=user)
            except Exception:
                pass
            raise
    return success(result)


@router.get("/upload-sessions/{session_id}", summary="查询上传会话")
def upload_session_detail(session_id: str, user=Depends(get_current_user)):
    from app.services.storage.production import get_upload_session

    return success(get_upload_session(session_id, user=user))


@router.post("/upload-sessions/{session_id}/complete", summary="COS HEAD 核验并完成上传会话")
def complete_upload_session(session_id: str, body: UploadSessionComplete, user=Depends(get_current_user)):
    from app.db.session import get_sessionmaker
    from app.models.file import FileObject
    from app.services.file_storage_governance_service import assign_retention
    from app.services.file_storage_quota_reservation_service import consume_quota
    from app.services.storage.production import complete_upload_session as complete_session

    result = complete_session(session_id, etag=body.etag, user=user)
    file_id = str(result.get("fileId") or "")
    if file_id.isdigit():
        db = get_sessionmaker()()
        try:
            row = db.get(FileObject, int(file_id), with_for_update=True)
            if row:
                consume_quota(
                    _session_reservation_key(session_id),
                    file_id=int(file_id),
                    db=db,
                )
                assign_retention(row, db=db)
                db.commit()
        finally:
            db.close()
    return success(result, message="上传完成，文件已进入安全扫描")


@router.post("/upload-sessions/{session_id}/abandon", summary="放弃未完成上传会话")
def abandon_upload_session(session_id: str, user=Depends(get_current_user)):
    from app.services.file_storage_quota_reservation_service import release_quota
    from app.services.storage.production import abandon_upload_session as abandon_session

    result = abandon_session(session_id, user=user)
    release_quota(_session_reservation_key(session_id), reason="COS_UPLOAD_SESSION_ABANDONED")
    return success(result, message="上传会话已放弃")


@router.get("/scan/health", summary="文件扫描服务健康状态")
def scan_health(user=Depends(require_permission_compat(FILE_GOVERNANCE_VIEW))):
    return success(health_snapshot())


@router.get("/{file_id}/scan-status", summary="查询文件安全扫描状态")
def scan_status(file_id: str, user=Depends(get_current_user)):
    meta = metadata_contract(file_id, user=user)
    return success({
        "fileId": meta.get("fileId"),
        "status": meta.get("status"),
        "scanRequired": meta.get("scanRequired", False),
        "scanStatus": meta.get("scanStatus"),
        "statusText": meta.get("statusText"),
        "scanAttempts": meta.get("scanAttempts", 0),
        "readyForBusiness": meta.get("readyForBusiness", False),
        "scannedAt": meta.get("scannedAt"),
        "allowedActions": meta.get("allowedActions") or [],
    })


@router.post("/{file_id}/scan-retry", summary="重试失败的文件安全扫描")
def scan_retry(file_id: str, user=Depends(require_permission_compat(FILE_SCAN_RETRY))):
    return success(retry_file_scan(file_id, user=user), message="已重新进入扫描队列")
