"""文件兼容 API：历史上传、扫描运维、元数据、安全下载与 COS 直传会话。"""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.file_contract import download_contract, metadata_contract, upload_contract
from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.core.permissions import require_permission
from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log
from app.services.file_scan_service import health_snapshot, retry_file_scan

router = APIRouter(tags=["S9·文件上传"])
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


@router.post("/upload", summary="上传文件（历史兼容入口，委托 POST /files 权威合同）")
async def upload_real(
    request: Request,
    file: UploadFile = File(...),
    bizType: str | None = Form(None),
    bizId: str | None = Form(None),
    user=Depends(get_current_user),
):
    effective_biz_type = bizType or request.query_params.get("bizType") or "ATTACHMENT"
    effective_biz_id = bizId if bizId not in (None, "") else request.query_params.get("bizId")
    data = await upload_contract(
        file,
        biz_type=effective_biz_type,
        biz_id=effective_biz_id,
        user=user,
        visibility="BIZ_SCOPED",
    )
    return success(data, message="上传成功；高风险文件需等待安全扫描")


@router.post("/upload-sessions", summary="创建 COS 精确对象直传会话")
def create_upload_session(body: UploadSessionCreate, user=Depends(get_current_user)):
    from app.services.storage.production import create_upload_session as create_session

    return success(create_session(
        filename=body.fileName,
        size_bytes=body.sizeBytes,
        sha256=body.sha256,
        biz_type=body.bizType,
        biz_id=body.bizId,
        client_type=body.clientType,
        idempotency_key=body.idempotencyKey,
        user=user,
    ))


@router.get("/upload-sessions/{session_id}", summary="查询上传会话")
def upload_session_detail(session_id: str, user=Depends(get_current_user)):
    from app.services.storage.production import get_upload_session

    return success(get_upload_session(session_id, user=user))


@router.post("/upload-sessions/{session_id}/complete", summary="COS HEAD 核验并完成上传会话")
def complete_upload_session(session_id: str, body: UploadSessionComplete, user=Depends(get_current_user)):
    from app.services.storage.production import complete_upload_session as complete_session

    return success(complete_session(session_id, etag=body.etag, user=user), message="上传完成，文件已进入安全扫描")


@router.post("/upload-sessions/{session_id}/abandon", summary="放弃未完成上传会话")
def abandon_upload_session(session_id: str, user=Depends(get_current_user)):
    from app.services.storage.production import abandon_upload_session as abandon_session

    return success(abandon_session(session_id, user=user), message="上传会话已放弃")


@router.get("/scan/health", summary="文件扫描服务健康状态")
def scan_health(user=Depends(require_permission("systemAdmin.file.manage"))):
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
def scan_retry(file_id: str, user=Depends(require_permission("systemAdmin.file.manage"))):
    return success(retry_file_scan(file_id, user=user), message="已重新进入扫描队列")


@router.get("/meta/{file_id}", summary="文件元数据与扫描状态（兼容入口）")
def file_meta(file_id: str, user=Depends(get_current_user)):
    return success(metadata_contract(file_id, user=user))


@router.get("/download/{file_id}", summary="下载附件（统一 resolver + 安全状态门禁）")
def download_file(file_id: str, user=Depends(get_current_user)):
    return download_contract(file_id, user=user)
